#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    visa.py - VISA completion and error messages
#
#    Copyright � 2005 Gregor Thalhammer <gth@users.sourceforge.net>,
#                     Torsten Bronger <bronger@physik.rwth-aachen.de>.
#
#    This file is part of pyvisa.
#
#    pyvisa is free software; you can redistribute it and/or modify it under
#    the terms of the GNU General Public License as published by the Free
#    Software Foundation; either version 2 of the License, or (at your option)
#    any later version.
#
#    pyvisa is distributed in the hope that it will be useful, but WITHOUT ANY
#    WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#    FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
#    details.
#
#    You should have received a copy of the GNU General Public License along
#    with pyvisa; if not, write to the Free Software Foundation, Inc., 59
#    Temple Place, Suite 330, Boston, MA 02111-1307 USA
#

"""visa.py defines an Python interface to the VISA library
"""

__version__ = "$Revision$"
# $Source$

from ctypes import *
from visa_messages import *
from vpp43_types import *
from vpp43_constants import *
import os

#load Visa library
if os.name == 'nt':
    visa = windll.visa32
elif os.name == 'posix':
    visa = cdll.visa #fix
else:
    raise "No implementation for your platform available."
    

class VisaError(IOError):
    """Base class for VISA errors"""
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        if self.value:
            (shortdesc, longdesc) = completion_and_error_messages[self.value]
            hexvalue = self.value #convert errorcodes (negative) to long
            if hexvalue < 0:
                hexvalue = hexvalue + 0x100000000L
            return shortdesc + " (%X): "%hexvalue + longdesc
            
#Checks return values for errors
def CheckStatus(status):
    #status = ViStatus(status).value
    if status < 0:
        raise VisaError(status)
    else:
        return status
    
#implement low level VISA functions

#VISA Resource Management
visa.viOpenDefaultRM.restype = CheckStatus
visa.viOpen.restype = CheckStatus
visa.viFindRsrc.restype = CheckStatus
visa.viFindNext.restype = CheckStatus
visa.viClose.restype    = CheckStatus

def OpenDefaultRM():
    """Return a session to the Default Resource Manager resource."""
    sesn = ViSession()
    result = visa.viOpenDefaultRM(byref(sesn))
    return (result, sesn.value)

def Open(sesn, rsrcName, accessMode, openTimeout):
    """Open a session to the specified device."""
    sesn = ViSession(sesn)
    rsrcName = ViRsrc(rsrcName)
    accessMode = ViAccessMode(accessMode)
    openTimout = ViUInt32(openTimeout)
    vi = ViSession()
    result = visa.viOpen(sesn, rsrcName, accessMode, openTimeout, byref(vi))
    return (result, vi.value)

def ParseRsrc(sesn, rsrcName):
    """Parse a resource string to get the interface information.

    This operation parses a resource string to verify its validity.
    It should succeed for all strings returned by viFindRsrc() and
    recognized by viOpen().  This operation is useful if you want to
    know what interface a given resource descriptor would use without
    actually opening a session to it.
 
    The values returned in intfType and intfNum correspond to the
    attributes VI_ATTR_INTF_TYPE and VI_ATTR_INTF_NUM. These values
    would be the same if a user opened that resource with viOpen() and
    queried the attributes with viGetAttribute()."""
    intfType = ViUInt16()
    intfNum = ViUInt16()
    result = visa.viParseRsrc(
        ViSession(sesn),
        ViRsrc(rsrcName),
        byref(intfType),
        byref(intfNum))
    return (result, intfType.value, intfNum.value)
    
def FindRsrc(session, expr):
    """Query a VISA system to locate the resources associated with a
    specified interface.

    This operation matches the value specified in the expr parameter
    with the resources available for a particular interface.

    In comparison to the original VISA function, this returns the
    complete list of found resources."""

    sesn = ViSession(session)
    expr = ViString(expr)
    findList = ViFindList()
    retcnt = ViUInt32()
    instrDesc = c_buffer('\000', 256)

    resource_list = []
    result = visa.viFindRsrc(sesn, expr, byref(findList), byref(retcnt), instrDesc)
    if result>=0:
        resource_list.append(instrDesc.value)
        for i in range(1, retcnt.value):
            visa.viFindNext(findList, instrDesc)
            resource_list.append(instrDesc.value)
        visa.viClose(findList)
    return resource_list

def Close(object):
    """Close the specified session, event, or find list.

    This operation closes a session, event, or a find list. In this
    process all the data structures that had been allocated for the
    specified vi are freed."""
    result = visa.viClose(ViObject(object))
    return result


#Basic I/O

visa.viWrite.restype = CheckStatus
def Write(vi, buf):
    vi = ViSession(vi)
    buf = c_buffer(buf, len(buf))
    count = ViUInt32(len(buf))
    retCount = ViUInt32()
    result = visa.viWrite(vi, buf, count, byref(retCount))
    return retCount.value

visa.viRead.restype = CheckStatus
def Read(vi, count):
    vi = ViSession(vi)
    buf = c_buffer(count)
    count = ViUInt32(count)
    retCount = ViUInt32()
    result = visa.viRead(vi, buf, count, byref(retCount))
    return (result, buf.raw[0:retCount.value])

visa.viGpibControlREN.restype = CheckStatus
def GpibControlREN(vi, mode):
    vi = ViSession(vi)
    mode = ViUInt16(mode)
    result = visa.viGpibControlREN(vi, mode)

#higher level classes and methods

class ResourceManager:
    def __init__(self):
        result, self.session = OpenDefaultRM()

    def __del__(self):
        Close(self.session)

    def find_resource(self, expression):
        resource_list = FindRsrc(self.session, expression)
        return resource_list

    def parse_resource(self, resource_name):
        result, interface_type, interface_number = \
                ParseRsrc(self.session, resource_name)

    def open(self, resourceName, exclusiveLock = None, loadConfig = None, openTimeout = 1000):
        accessMode = 0
        if exclusiveLock:
            accessMode = accessMode | VI_EXCLUSIVE_LOCK
        if loadConfig:
            accessMode = accessMode | VI_LOAD_CONFIG
        result, vi = Open(self.session, resourceName, accessMode, openTimeout)
        return Resource(vi.value)


class Resource:
    def __init__(self, vi):
        self.session = vi

    def write(self, buf):
        return Write(self.session, buf)

    def read(self, maxcount = None):
        if maxcount:
            result, buf = Read(self.session, maxcount)
            return buf
        else:
            accumbuf = ''
            while 1:
                result, buf = Read(self.session, 1024)
                accumbuf = accumbuf + buf
                if result in (VI_SUCCESS, VI_SUCCESS_TERM_CHAR):
                    return accumbuf
    def setlocal(self):
        VI_GPIB_REN_DEASSERT        = 0 
        VI_GPIB_REN_ASSERT          = 1
        VI_GPIB_REN_DEASSERT_GTL    = 2
        VI_GPIB_REN_ASSERT_ADDRESS  = 3
        VI_GPIB_REN_ASSERT_LLO      = 4
        VI_GPIB_REN_ASSERT_ADDRESS_LLO = 5
        VI_GPIB_REN_ADDRESS_GTL     = 6
        mode = 6

        
        #Test Marconi 2019: 0 local, 1 remote, 2 local, 4 local lockout, 5 local, 6 local

        GpibControlREN(self.session, mode)
        
    def close(self):
        Close(self.session)
    
class ResourceManager:
    def __init__(self):
        result, self.session = OpenDefaultRM()

    def __del__(self):
        Close(self.session)

    def find_resource(self, expression):
        return FindRsrc(self.session, expression)

    def open(self, resourceName, exclusiveLock = None, loadConfig = None, openTimeout = 1000):
        accessMode = 0
        if exclusiveLock:
            accessMode = accessMode | VI_EXCLUSIVE_LOCK
        if loadConfig:
            accessMode = accessMode | VI_LOAD_CONFIG
        result, vi = Open(self.session, resourceName, accessMode, openTimeout)
        return Resource(vi)

#_RM = ResourceManager() #liefert Exception in __del__ beim Beenden
#open = _RM.Open
#find_resource = _RM.FindResource