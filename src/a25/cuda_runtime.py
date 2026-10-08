"""Process-local CUDA wait policy; model arithmetic/accounting are unchanged."""
from __future__ import annotations
import ctypes
import os

def configure_host_wait(policy="default", device=0):
    if policy == "default":
        return {"policy": "default", "changed": False}
    if policy != "blocking_sync":
        raise ValueError("EXPLICIT_CUDA_WAIT_POLICY_REQUIRED")
    library = ctypes.WinDLL("nvcuda.dll") if os.name == "nt" else ctypes.CDLL("libcuda.so.1")
    def invoke(name, argtypes, *args):
        function = getattr(library, name)
        function.argtypes, function.restype = argtypes, ctypes.c_int
        result = function(*args)
        if result:
            raise RuntimeError("CUDA_DRIVER_WAIT_POLICY_FAILED:" + name + ":" + str(result))
    invoke("cuInit", [ctypes.c_uint], 0)
    native_device = ctypes.c_int()
    invoke("cuDeviceGet", [ctypes.POINTER(ctypes.c_int), ctypes.c_int], ctypes.byref(native_device), int(device))
    flags, active = ctypes.c_uint(), ctypes.c_int()
    state_types = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_int)]
    invoke("cuDevicePrimaryCtxGetState", state_types, native_device, ctypes.byref(flags), ctypes.byref(active))
    old, target = flags.value, (flags.value & ~7) | 4  # CU_CTX_SCHED_BLOCKING_SYNC.
    if active.value and (flags.value & 7) != 4:
        raise RuntimeError("CUDA_PRIMARY_CONTEXT_ALREADY_ACTIVE; never reset a live context")
    function = "cuDevicePrimaryCtxSetFlags_v2" if hasattr(library, "cuDevicePrimaryCtxSetFlags_v2") else "cuDevicePrimaryCtxSetFlags"
    invoke(function, [ctypes.c_int, ctypes.c_uint], native_device, target)
    invoke("cuDevicePrimaryCtxGetState", state_types, native_device, ctypes.byref(flags), ctypes.byref(active))
    if (flags.value & 7) != 4:
        raise RuntimeError("CUDA_BLOCKING_WAIT_NOT_APPLIED")
    return {"policy": policy, "old_flags": old, "applied_flags": flags.value,
            "context_active_at_configuration": bool(active.value), "changed": old != flags.value,
            "physics_precision_or_tolerances_changed": False}
