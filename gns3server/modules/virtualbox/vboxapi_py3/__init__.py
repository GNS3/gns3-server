"""
Copyright (C) 2009-2012 Oracle Corporation

This file is part of VirtualBox Open Source Edition (OSE), as
available from http://www.virtualbox.org. This file is free software;
you can redistribute it and/or modify it under the terms of the GNU
General Public License (GPL) as published by the Free Software
Foundation, in version 2 as it comes in the "COPYING" file of the
VirtualBox OSE distribution. VirtualBox OSE is distributed in the
hope that it will be useful, but WITHOUT ANY WARRANTY of any kind.
"""

import sys,os
import traceback

# To set Python bitness on OSX use 'export VERSIONER_PYTHON_PREFER_32_BIT=yes'

VboxBinDir = os.environ.get("VBOX_PROGRAM_PATH", None)
VboxSdkDir = os.environ.get("VBOX_SDK_PATH", None)

if VboxBinDir is None:
    # Will be set by the installer
    VboxBinDir = "C:\\Program Files\\Oracle\\VirtualBox\\"

if VboxSdkDir is None:
    # Will be set by the installer
    VboxSdkDir = "C:\\Program Files\\Oracle\\VirtualBox\\sdk\\"

os.environ["VBOX_PROGRAM_PATH"] = VboxBinDir
os.environ["VBOX_SDK_PATH"] = VboxSdkDir
sys.path.append(VboxBinDir)

from .VirtualBox_constants import VirtualBoxReflectionInfo

class PerfCollector:
    """ This class provides a wrapper over IPerformanceCollector in order to
    get more 'pythonic' interface.

    To begin collection of metrics use setup() method.

    To get collected data use query() method.

    It is possible to disable metric collection without changing collection
    parameters with disable() method. The enable() method resumes metric
    collection.
    """

    def __init__(self, mgr, vbox):
        """ Initializes the instance.

        """
        self.mgr = mgr
        self.isMscom = (mgr.type == 'MSCOM')
        self.collector = vbox.performanceCollector

    def setup(self, names, objects, period, nsamples):
        """ Discards all previously collected values for the specified
        metrics, sets the period of collection and the number of retained
        samples, enables collection.
        """
        self.collector.setupMetrics(names, objects, period, nsamples)

    def enable(self, names, objects):
        """ Resumes metric collection for the specified metrics.
        """
        self.collector.enableMetrics(names, objects)

    def disable(self, names, objects):
        """ Suspends metric collection for the specified metrics.
        """
        self.collector.disableMetrics(names, objects)

    def query(self, names, objects):
        """ Retrieves collected metric values as well as some auxiliary
        information. Returns an array of dictionaries, one dictionary per
        metric. Each dictionary contains the following entries:
        'name': metric name
        'object': managed object this metric associated with
        'unit': unit of measurement
        'scale': divide 'values' by this number to get float numbers
        'values': collected data
        'values_as_string': pre-processed values ready for 'print' statement
        """
        # Get around the problem with input arrays returned in output
        # parameters (see #3953) for MSCOM.
        if self.isMscom:
            (values, names, objects, names_out, objects_out, units, scales, sequence_numbers,
                indices, lengths) = self.collector.queryMetricsData(names, objects)
        else:
            (values, names_out, objects_out, units, scales, sequence_numbers,
                indices, lengths) = self.collector.queryMetricsData(names, objects)
        out = []
        for i in xrange(0, len(names_out)):
            scale = int(scales[i])
            if scale != 1:
                fmt = '%.2f%s'
            else:
                fmt = '%d %s'
            out.append({
                'name':str(names_out[i]),
                'object':str(objects_out[i]),
                'unit':str(units[i]),
                'scale':scale,
                'values':[int(values[j]) for j in xrange(int(indices[i]), int(indices[i])+int(lengths[i]))],
                'values_as_string':'['+', '.join([fmt % (int(values[j])/scale, units[i]) for j in xrange(int(indices[i]), int(indices[i])+int(lengths[i]))])+']'
            })
        return out

def ComifyName(name):
    return name[0].capitalize()+name[1:]

_COMForward = { 'getattr' : None,
                'setattr' : None}

def CustomGetAttr(self, attr):
    # fastpath
    if self.__class__.__dict__.get(attr) != None:
        return self.__class__.__dict__.get(attr)

    # try case-insensitivity workaround for class attributes (COM methods)
    for k in self.__class__.__dict__.keys():
        if k.lower() == attr.lower():
            setattr(self.__class__, attr, self.__class__.__dict__[k])
            return getattr(self, k)
    try:
        return _COMForward['getattr'](self,ComifyName(attr))
    except AttributeError:
        return _COMForward['getattr'](self,attr)

def CustomSetAttr(self, attr, value):
    try:
        return _COMForward['setattr'](self, ComifyName(attr), value)
    except AttributeError:
        return _COMForward['setattr'](self, attr, value)

class PlatformMSCOM:
    # Class to fake access to constants in style of foo.bar.boo
    class ConstantFake:
        def __init__(self, parent, name):
            self.__dict__['_parent'] = parent
            self.__dict__['_name'] = name
            self.__dict__['_consts'] = {}
            try:
                self.__dict__['_depth']=parent.__dict__['_depth']+1
            except:
                self.__dict__['_depth']=0
                if self.__dict__['_depth'] > 4:
                    raise AttributeError

        def __getattr__(self, attr):
            import win32com
            from win32com.client import constants

            if attr.startswith("__"):
                raise AttributeError

            consts = self.__dict__['_consts']

            fake = consts.get(attr, None)
            if fake != None:
               return fake
            try:
               name = self.__dict__['_name']
               parent = self.__dict__['_parent']
               while parent != None:
                  if parent._name is not None:
                    name = parent._name+'_'+name
                  parent = parent._parent

               if name is not None:
                  name += "_" + attr
               else:
                  name = attr
               return win32com.client.constants.__getattr__(name)
            except AttributeError as e:
               fake = PlatformMSCOM.ConstantFake(self, attr)
               consts[attr] = fake
               return fake


    class InterfacesWrapper:
            def __init__(self):
                self.__dict__['_rootFake'] = PlatformMSCOM.ConstantFake(None, None)

            def __getattr__(self, a):
                import win32com
                from win32com.client import constants
                if a.startswith("__"):
                    raise AttributeError
                try:
                    return win32com.client.constants.__getattr__(a)
                except AttributeError as e:
                    return self.__dict__['_rootFake'].__getattr__(a)

    VBOX_TLB_GUID  = '{46137EEC-703B-4FE5-AFD4-7C9BBBBA0259}'
    VBOX_TLB_LCID  = 0
    VBOX_TLB_MAJOR = 1
    VBOX_TLB_MINOR = 0

    def __init__(self, params):
            from win32com import universal
            from win32com.client import gencache, DispatchBaseClass
            from win32com.client import constants, getevents
            import win32com
            import pythoncom
            import win32api
            from win32con import DUPLICATE_SAME_ACCESS
            from win32api import GetCurrentThread,GetCurrentThreadId,DuplicateHandle,GetCurrentProcess
            import threading
            pid = GetCurrentProcess()
            self.tid = GetCurrentThreadId()
            handle = DuplicateHandle(pid, GetCurrentThread(), pid, 0, 0, DUPLICATE_SAME_ACCESS)
            self.handles = []
            self.handles.append(handle)
            _COMForward['getattr'] = DispatchBaseClass.__dict__['__getattr__']
            DispatchBaseClass.__getattr__ = CustomGetAttr
            _COMForward['setattr'] = DispatchBaseClass.__dict__['__setattr__']
            DispatchBaseClass.__setattr__ = CustomSetAttr
            win32com.client.gencache.EnsureDispatch('VirtualBox.Session')
            win32com.client.gencache.EnsureDispatch('VirtualBox.VirtualBox')
            self.oIntCv = threading.Condition()
            self.fInterrupted = False;

    def getSessionObject(self, vbox):
        import win32com
        from win32com.client import Dispatch
        return win32com.client.Dispatch("VirtualBox.Session")

    def getVirtualBox(self):
        import win32com
        from win32com.client import Dispatch
        return win32com.client.Dispatch("VirtualBox.VirtualBox")

    def getType(self):
        return 'MSCOM'

    def getRemote(self):
        return False

    def getArray(self, obj, field):
        return obj.__getattr__(field)

    def initPerThread(self):
        import pythoncom
        pythoncom.CoInitializeEx(0)

    def deinitPerThread(self):
        import pythoncom
        pythoncom.CoUninitialize()

    def createListener(self, impl, arg):
        d = {}
        d['BaseClass'] = impl
        d['arg'] = arg
        d['tlb_guid'] = PlatformMSCOM.VBOX_TLB_GUID
        str = ""
        str += "import win32com.server.util\n"
        str += "import pythoncom\n"

        str += "class ListenerImpl(BaseClass):\n"
        str += "   _com_interfaces_ = ['IEventListener']\n"
        str += "   _typelib_guid_ = tlb_guid\n"
        str += "   _typelib_version_ = 1, 0\n"
        str += "   _reg_clsctx_ = pythoncom.CLSCTX_INPROC_SERVER\n"
        # Maybe we'd better implement Dynamic invoke policy, to be more flexible here
        str += "   _reg_policy_spec_ = 'win32com.server.policy.EventHandlerPolicy'\n"

        # capitalized version of listener method
        str += "   HandleEvent=BaseClass.handleEvent\n"
        str += "   def __init__(self): BaseClass.__init__(self, arg)\n"
        str += "result = win32com.server.util.wrap(ListenerImpl())\n"
        exec(str,d,d)
        return d['result']

    def waitForEvents(self, timeout):
        from win32api import GetCurrentThreadId
        from win32event import INFINITE
        from win32event import MsgWaitForMultipleObjects, \
                               QS_ALLINPUT, WAIT_TIMEOUT, WAIT_OBJECT_0
        from pythoncom import PumpWaitingMessages
        import types

        if not isinstance(timeout, types.IntType):
            raise TypeError("The timeout argument is not an integer")
        if (self.tid != GetCurrentThreadId()):
            raise Exception("wait for events from the same thread you inited!")

        if timeout < 0:     cMsTimeout = INFINITE
        else:               cMsTimeout = timeout
        rc = MsgWaitForMultipleObjects(self.handles, 0, cMsTimeout, QS_ALLINPUT)
        if rc >= WAIT_OBJECT_0 and rc < WAIT_OBJECT_0+len(self.handles):
            # is it possible?
            rc = 2;
        elif rc==WAIT_OBJECT_0 + len(self.handles):
            # Waiting messages
            PumpWaitingMessages()
            rc = 0;
        else:
            # Timeout
            rc = 1;

        # check for interruption
        self.oIntCv.acquire()
        if self.fInterrupted:
            self.fInterrupted = False
            rc = 1;
        self.oIntCv.release()

        return rc;

    def interruptWaitEvents(self):
        """
        Basically a python implementation of EventQueue::postEvent().

        The magic value must be in sync with the C++ implementation or this
        won't work.

        Note that because of this method we cannot easily make use of a
        non-visible Window to handle the message like we would like to do.
        """
        from win32api import PostThreadMessage
        from win32con import WM_USER
        self.oIntCv.acquire()
        self.fInterrupted = True
        self.oIntCv.release()
        try:
            PostThreadMessage(self.tid, WM_USER, None, 0xf241b819)
        except:
            return False;
        return True;

    def deinit(self):
        import pythoncom
        from win32file import CloseHandle

        for h in self.handles:
           if h is not None:
              CloseHandle(h)
        self.handles = None
        pythoncom.CoUninitialize()
        pass

    def queryInterface(self, obj, klazzName):
        from win32com.client import CastTo
        return CastTo(obj, klazzName)

class PlatformXPCOM:
    def __init__(self, params):
        sys.path.append(VboxSdkDir+'/bindings/xpcom/python/')
        import xpcom.vboxxpcom
        import xpcom
        import xpcom.components

    def getSessionObject(self, vbox):
        import xpcom.components
        return xpcom.components.classes["@virtualbox.org/Session;1"].createInstance()

    def getVirtualBox(self):
        import xpcom.components
        return xpcom.components.classes["@virtualbox.org/VirtualBox;1"].createInstance()

    def getType(self):
        return 'XPCOM'

    def getRemote(self):
        return False

    def getArray(self, obj, field):
        return obj.__getattr__('get'+ComifyName(field))()

    def initPerThread(self):
        import xpcom
        xpcom._xpcom.AttachThread()

    def deinitPerThread(self):
        import xpcom
        xpcom._xpcom.DetachThread()

    def createListener(self, impl, arg):
        d = {}
        d['BaseClass'] = impl
        d['arg'] = arg
        str = ""
        str += "import xpcom.components\n"
        str += "class ListenerImpl(BaseClass):\n"
        str += "   _com_interfaces_ = xpcom.components.interfaces.IEventListener\n"
        str += "   def __init__(self): BaseClass.__init__(self, arg)\n"
        str += "result = ListenerImpl()\n"
        exec(str,d,d)
        return d['result']

    def waitForEvents(self, timeout):
        import xpcom
        return xpcom._xpcom.WaitForEvents(timeout)

    def interruptWaitEvents(self):
        import xpcom
        return xpcom._xpcom.InterruptWait()

    def deinit(self):
        import xpcom
        xpcom._xpcom.DeinitCOM()

    def queryInterface(self, obj, klazzName):
        import xpcom.components
        return obj.queryInterface(getattr(xpcom.components.interfaces, klazzName))

class PlatformWEBSERVICE:
    def __init__(self, params):
        sys.path.append(os.path.join(VboxSdkDir,'bindings', 'webservice', 'python', 'lib'))
        #import VirtualBox_services
        import VirtualBox_wrappers
        from VirtualBox_wrappers import IWebsessionManager2

        if params is not None:
            self.user = params.get("user", "")
            self.password = params.get("password", "")
            self.url = params.get("url", "")
        else:
            self.user = ""
            self.password = ""
            self.url = None
        self.vbox = None

    def getSessionObject(self, vbox):
        return self.wsmgr.getSessionObject(vbox)

    def getVirtualBox(self):
        return self.connect(self.url, self.user, self.password)

    def connect(self, url, user, passwd):
        if self.vbox is not None:
             self.disconnect()
        from VirtualBox_wrappers import IWebsessionManager2
        if url is None:
            url = ""
        self.url = url
        if user is None:
            user = ""
        self.user = user
        if passwd is None:
            passwd = ""
        self.password = passwd
        self.wsmgr = IWebsessionManager2(self.url)
        self.vbox = self.wsmgr.logon(self.user, self.password)
        if not self.vbox.handle:
            raise Exception("cannot connect to '"+self.url+"' as '"+self.user+"'")
        return self.vbox

    def disconnect(self):
        if self.vbox is not None and self.wsmgr is not None:
                self.wsmgr.logoff(self.vbox)
                self.vbox = None
                self.wsmgr = None

    def getType(self):
        return 'WEBSERVICE'

    def getRemote(self):
        return True

    def getArray(self, obj, field):
        return obj.__getattr__(field)

    def initPerThread(self):
        pass

    def deinitPerThread(self):
        pass

    def createListener(self, impl, arg):
        raise Exception("no active listeners for webservices")

    def waitForEvents(self, timeout):
        # Webservices cannot do that yet
        return 2;

    def interruptWaitEvents(self, timeout):
        # Webservices cannot do that yet
        return False;

    def deinit(self):
        try:
           disconnect()
        except:
           pass

    def queryInterface(self, obj, klazzName):
        d = {}
        d['obj'] = obj
        str = ""
        str += "from VirtualBox_wrappers import "+klazzName+"\n"
        str += "result = "+klazzName+"(obj.mgr,obj.handle)\n"
        # wrong, need to test if class indeed implements this interface
        exec(str,d,d)
        return d['result']

class SessionManager:
    def __init__(self, mgr):
        self.mgr = mgr

    def getSessionObject(self, vbox):
        return self.mgr.platform.getSessionObject(vbox)

class VirtualBoxManager:
    def __init__(self, style, platparams):
        if style is None:
            if sys.platform == 'win32':
                style = "MSCOM"
            else:
                style = "XPCOM"


        exec("self.platform = Platform"+style+"(platparams)")
        # for webservices, enums are symbolic
        self.constants = VirtualBoxReflectionInfo(style == "WEBSERVICE")
        self.type = self.platform.getType()
        self.remote = self.platform.getRemote()
        self.style = style
        self.mgr = SessionManager(self)

        try:
            self.vbox = self.platform.getVirtualBox()
        except NameError as ne:
            print("Installation problem: check that appropriate libs in place")
            traceback.print_exc()
            raise ne
        except Exception as e:
            print("init exception: ",e)
            traceback.print_exc()
            if self.remote:
                self.vbox = None
            else:
                raise e

    def getArray(self, obj, field):
        return self.platform.getArray(obj, field)

    def getVirtualBox(self):
        return  self.platform.getVirtualBox()

    def __del__(self):
        self.deinit()

    def deinit(self):
        if hasattr(self, "vbox"):
            del self.vbox
            self.vbox = None
        if hasattr(self, "platform"):
            self.platform.deinit()
            self.platform = None

    def initPerThread(self):
        self.platform.initPerThread()

    def openMachineSession(self, mach, permitSharing = True):
         session = self.mgr.getSessionObject(self.vbox)
         if permitSharing:
             type = self.constants.LockType_Shared
         else:
             type = self.constants.LockType_Write
         mach.lockMachine(session, type)
         return session

    def closeMachineSession(self, session):
        if session is not None:
            session.unlockMachine()

    def deinitPerThread(self):
        self.platform.deinitPerThread()

    def createListener(self, impl, arg = None):
        return self.platform.createListener(impl, arg)

    def waitForEvents(self, timeout):
        """
        Wait for events to arrive and process them.

        The timeout is in milliseconds.  A negative value means waiting for
        ever, while 0 does not wait at all.

        Returns 0 if events was processed.
        Returns 1 if timed out or interrupted in some way.
        Returns 2 on error (like not supported for web services).

        Raises an exception if the calling thread is not the main thread (the one
        that initialized VirtualBoxManager) or if the time isn't an integer.
        """
        return self.platform.waitForEvents(timeout)

    def interruptWaitEvents(self):
        """
        Interrupt a waitForEvents call.
        This is normally called from a worker thread.

        Returns True on success, False on failure.
        """
        return self.platform.interruptWaitEvents()

    def getPerfCollector(self, vbox):
        return PerfCollector(self, vbox)

    def getBinDir(self):
        global VboxBinDir
        return VboxBinDir

    def getSdkDir(self):
        global VboxSdkDir
        return VboxSdkDir

    def queryInterface(self, obj, klazzName):
        return self.platform.queryInterface(obj, klazzName)
