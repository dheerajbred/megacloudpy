import asyncio
import base64
import hashlib
from io import BytesIO
import json
import os
import re
import struct
import time
from typing import Any, Literal

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import PIL.Image
import aiohttp
from numpy import array
from rich.console import Console
from wasmtime import (
    Engine,
    Func,
    FuncType,
    Instance,
    Linker,
    Memory,
    Module,
    Store,
    ValType,
)

from wasm_png import data_url

console = Console()

# wasm
engine = Engine()
store = Store(engine)
wasm: Instance
wasm_memory: Memory

# other
arr: list[Any] = [None] * 128
pointer = len(arr)
size: int
user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
date_now = int(time.time() * 1000)
logging = False


def inspect_class(obj, depth=0):
    indent = "  " * depth

    print(type(obj).__name__)
    for prop in dir(obj):
        if prop.startswith("__"):
            continue

        val = getattr(obj, prop)

        if hasattr(val, "__dict__"):
            print(f"{indent}{prop}: ", end="")
            inspect_class(val, depth + 1)

        elif callable(val):
            print(f"{indent}{prop}()")

        elif isinstance(val, list):
            print(f"{indent}{prop}: ({len(val)}) {val[:60]}")

        elif isinstance(val, bytearray):
            print(f"{indent}{prop}: ({len(val)}) {val.hex()[:40]}")

        else:
            print(f"{indent}{prop}: {val}")


class Meta:
    content: str


class ImageData:
    height = 50
    width = 65
    data: list[int]


# canvas
class Style2:
    display = "inline"


class Style:
    style = Style2()


class Canvas:
    baseUrl = ""
    width = 0
    height = 0
    style = Style()
    context2d = {}


# fake window
class LocalStorage:
    kversion: str
    kid: str

    def setItem(self, item, value):
        setattr(self, item, value)


class Navigator:
    webdriver = False
    userAgent = user_agent


class Document:
    cookie = ""


class Location:
    href = ""
    origin = ""


class Performance:
    timeOrigin = date_now


class FakeWindow:
    localStorage = LocalStorage()
    error = False
    navigator = Navigator()
    length = 0
    document = Document()
    origin: str
    location = Location()
    performance = Performance()
    xrax: str
    c = False
    G: str

    def z(self, value):
        return [
            (0xFF000000 & value) >> 24,
            (0x00FF0000 & value) >> 16,
            (0x0000FF00 & value) >> 8,
            0x000000FF & value,
        ]

    crypto = {}
    msCrypto = {}
    browser_version = 1878522368
    pid: str

    def navigate(self) -> bytes: ...
    def jwt_plugin(self, wasm: bytearray) -> None: ...


# node list
class Image:
    src = ""
    height = 50
    width = 65
    complete = True


class NodeList:
    image = Image()
    context2d = {}
    length = 1


meta = Meta()
image_data = ImageData()
canvas = Canvas()
fake_window = FakeWindow()
node_list = NodeList()


def get_wasm_memory() -> Memory:
    return wasm.exports(store)["memory"]  # type: ignore


def write_to_memory(data, offset: int) -> None:
    buffer = get_memory_buffer()

    if isinstance(data, bytes) or isinstance(data, bytearray):
        buffer[offset : offset + len(data)] = data

    else:
        raise ValueError(f"can't write '{type(data).__name__}' type")

    wasm_memory.write(store, buffer)


def set_float64(offset: int, value: int) -> None:
    write_to_memory(struct.pack("<d", value), offset)


def set_int32(offset: int, value: int) -> None:
    write_to_memory(value.to_bytes(4, "little"), offset)


async def make_request(
    url: str,
    headers: dict,
    params: dict,
    func,
):
    async with aiohttp.ClientSession() as client:
        async with client.get(url, headers=headers, params=params) as resp:
            return await func(resp)


async def get_pixel_arr(url: str) -> list[int]:
    async with aiohttp.ClientSession() as client:
        async with client.get(url) as resp:
            data = await resp.read()

    image = PIL.Image.open(BytesIO(data))
    return array(image).flatten().tolist()


def is_null(obj):
    return obj is None


def get(index: int) -> Any:
    return arr[index]


def parse(text: str) -> int:
    global size

    buffer = bytearray()
    text_len = len(text)
    offset = export0(text_len, 1)
    i = 0

    for char in text:
        char_code = ord(char)

        if char_code > 127:
            break

        buffer.append(char_code)
        i += 1

    write_to_memory(buffer, offset)
    size = i

    return offset


def get_memory_buffer() -> bytearray:
    return wasm_memory.read(store)


def shift(index: int) -> None:
    global pointer

    if index >= 132:
        arr[index] = pointer
        pointer = index


def shift_get(index: int):
    item = get(index)
    shift(index)

    return item


def decode_sub(index: int, offset: int) -> str:
    index = index & 0xFFFFFFFF

    return get_memory_buffer()[index : index + offset].decode()


def add_to_stack(obj) -> int:
    global arr, pointer

    if pointer == len(arr):
        arr.append(len(arr) + 1)

    Qn = pointer
    pointer = get(Qn)
    arr[Qn] = obj

    return Qn


def args(QP, Qn, QT, func):
    Qx = {"a": QP, "b": Qn, "cnt": 1, "dtor": QT}
    __wbindgen_export_2 = wasm.exports(store)["__wbindgen_export_2"]

    def wrapped(*Qw):
        Qx["cnt"] += 1
        try:
            return func(Qx["a"], Qx["b"], *Qw)
        finally:
            Qx["cnt"] -= 1
            if Qx["cnt"] == 0:
                __wbindgen_export_2.get(store, Qx["dtor"])(Qx["a"], Qx["b"])  # type: ignore

                Qx["a"] = 0

    setattr(wrapped, "original", Qx)

    return wrapped


def export0(Qp, Qn) -> int:
    __wbindgen_export_0 = wasm.exports(store)["__wbindgen_export_0"]
    return __wbindgen_export_0(store, Qp, Qn) & 0xFFFFFFFF  # type: ignore


def export3(Qp, Qn) -> int:
    __wbindgen_export_3 = wasm.exports(store)["__wbindgen_export_3"]
    return shift_get(__wbindgen_export_3(store, Qp, Qn))  # type: ignore


def export4(Qy, QO, Qx):
    __wbindgen_export_4 = wasm.exports(store)["__wbindgen_export_4"]
    __wbindgen_export_4(store, Qy, QO, add_to_stack(Qx))  # type: ignore


def export5(Qp, Qn):
    __wbindgen_export_4 = wasm.exports(store)["__wbindgen_export_5"]
    __wbindgen_export_4(store, Qp, Qn)  # type: ignore


def write_png(decoded_png):
    global size

    png_len = len(decoded_png)
    size = png_len

    offset = export0(png_len, 1)
    write_to_memory(bytearray(decoded_png), offset)

    return offset


def is_response(obj) -> bool:
    return isinstance(obj, aiohttp.ClientResponse)


def load_wasm_imports() -> Linker:
    linker = Linker(engine)

    def add_import_func(type: FuncType, func, name: str | None = None):
        linker.define(store, "wbg", func.__name__ if not name else name, Func(store, type, func))

    TYPE0 = FuncType([ValType.i32(), ValType.i32()], [ValType.i32()])
    TYPE1 = FuncType([ValType.i32(), ValType.i32(), ValType.i32()], [ValType.i32()])
    TYPE2 = FuncType([ValType.i32(), ValType.i32()], [])
    TYPE3 = FuncType([ValType.i32()], [ValType.i32()])
    TYPE4 = FuncType([ValType.i32(), ValType.i32(), ValType.i32()], [])
    TYPE5 = FuncType([ValType.i32()], [])
    TYPE6 = FuncType([ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32()], [])
    TYPE7 = FuncType([ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32()], [])
    TYPE8 = FuncType([], [ValType.i32()])
    TYPE11 = FuncType([ValType.i32(), ValType.f64(), ValType.f64(), ValType.f64(), ValType.f64()], [])
    TYPE15 = FuncType([ValType.i32(), ValType.f64()], [])
    TYPE16 = FuncType([ValType.i32(), ValType.i32(), ValType.f64(), ValType.f64()], [])
    TYPE17 = FuncType([ValType.i32(), ValType.f64(), ValType.f64(), ValType.f64(), ValType.f64()], [ValType.i32()])
    TYPE18 = FuncType([ValType.i32(), ValType.i32(), ValType.i32(), ValType.f64(), ValType.f64()], [])
    TYPE19 = FuncType([ValType.i32()], [ValType.f64()])

    def __wbindgen_is_undefined(index):
        obj = get(index)
        return is_null(obj)

    add_import_func(TYPE3, __wbindgen_is_undefined)

    def __wbindgen_is_null(*_):
        return False

    add_import_func(TYPE3, __wbindgen_is_null)

    def __wbindgen_string_get(offset, index):
        string = get(index)
        val = parse(string)

        set_int32(offset + 4, size)
        set_int32(offset, val)

    add_import_func(TYPE2, __wbindgen_string_get)

    def __wbindgen_object_drop_ref(index):
        shift_get(index)

    add_import_func(TYPE5, __wbindgen_object_drop_ref)

    def __wbindgen_cb_drop(index):
        org = shift_get(index).original
        org["cnt"] -= 1

        if org["cnt"] == 1:
            org["a"] = 0
            return True

        return False

    add_import_func(TYPE3, __wbindgen_cb_drop)

    def __wbindgen_string_new(index, offset):
        string = decode_sub(index, offset)
        return add_to_stack(string)

    add_import_func(TYPE0, __wbindgen_string_new)

    def __wbindgen_boolean_get(index):
        boolean = get(index)
        return 1 if boolean else 0 if isinstance(boolean, bool) else 2

    add_import_func(TYPE3, __wbindgen_boolean_get)

    def __wbindgen_number_get(offset, index):
        number = get(index)

        set_float64(offset + 8, 0 if is_null(number) else number)
        set_int32(offset, 0 if is_null(number) else 1)

    add_import_func(TYPE2, __wbindgen_number_get)

    def __wbg_instanceof_CanvasRenderingContext2d_4ec30ddd3f29f8f9(_):
        return True

    add_import_func(TYPE3, __wbg_instanceof_CanvasRenderingContext2d_4ec30ddd3f29f8f9)

    def __wbg_setfillStyle_59f426135f52910f(*_):
        pass

    add_import_func(TYPE2, __wbg_setfillStyle_59f426135f52910f)

    def __wbg_setshadowBlur_229c56539d02f401(*_):
        pass

    add_import_func(TYPE15, __wbg_setshadowBlur_229c56539d02f401)

    def __wbg_setshadowColor_340d5290cdc4ae9d(*_):
        pass

    add_import_func(TYPE4, __wbg_setshadowColor_340d5290cdc4ae9d)

    def __wbg_setfont_16d6e31e06a420a5(*_):
        pass

    add_import_func(TYPE4, __wbg_setfont_16d6e31e06a420a5)

    def __wbg_settextBaseline_c3266d3bd4a6695c(*_):
        pass

    add_import_func(TYPE4, __wbg_settextBaseline_c3266d3bd4a6695c)

    def __wbg_drawImage_cb13768a1bdc04bd(*_):
        pass

    add_import_func(TYPE16, __wbg_drawImage_cb13768a1bdc04bd)

    def __wbg_getImageData_66269d289f37d3c7(*_):
        return add_to_stack(image_data)

    add_import_func(TYPE17, __wbg_getImageData_66269d289f37d3c7)

    def __wbg_rect_2fa1df87ef638738(*_):
        pass

    add_import_func(TYPE11, __wbg_rect_2fa1df87ef638738)

    def __wbg_fillRect_4dd28e628381d240(*_):
        pass

    add_import_func(TYPE11, __wbg_fillRect_4dd28e628381d240)

    def __wbg_fillText_07e5da9e41652f20(*_):
        pass

    add_import_func(TYPE18, __wbg_fillText_07e5da9e41652f20)

    def __wbg_setProperty_5144ddce66bbde41(*_):
        pass

    add_import_func(TYPE7, __wbg_setProperty_5144ddce66bbde41)

    def __wbg_createElement_03cf347ddad1c8c0(*_):
        return add_to_stack(canvas)

    add_import_func(TYPE1, __wbg_createElement_03cf347ddad1c8c0)

    def __wbg_querySelector_118a0639aa1f51cd(*_):
        return add_to_stack(meta)

    add_import_func(TYPE1, __wbg_querySelector_118a0639aa1f51cd)

    def __wbg_querySelectorAll_50c79cd4f7573825(*_):
        return add_to_stack(node_list)

    add_import_func(TYPE1, __wbg_querySelectorAll_50c79cd4f7573825)

    def __wbg_getAttribute_706ae88bd37410fa(offset, *_):
        attr = meta.content
        todo = 0 if is_null(attr) else parse(attr)

        set_int32(offset + 4, size)
        set_int32(offset, todo)

    add_import_func(TYPE6, __wbg_getAttribute_706ae88bd37410fa)

    def __wbg_target_6795373f170fd786(index):
        obj = get(index)
        return add_to_stack(obj)

    add_import_func(TYPE3, __wbg_target_6795373f170fd786)

    def __wbg_addEventListener_f984e99465a6a7f4():
        pass

    add_import_func(TYPE6, __wbg_addEventListener_f984e99465a6a7f4)

    def __wbg_instanceof_HtmlCanvasElement_1e81f71f630e46bc(_):
        return True

    add_import_func(TYPE3, __wbg_instanceof_HtmlCanvasElement_1e81f71f630e46bc)

    def __wbg_setwidth_233645b297bb3318(index, set):
        get(index).width = set & 0xFFFFFFFF

    add_import_func(TYPE2, __wbg_setwidth_233645b297bb3318)

    def __wbg_setheight_fcb491cf54e3527c(index, set):
        get(index).height = set & 0xFFFFFFFF

    add_import_func(TYPE2, __wbg_setheight_fcb491cf54e3527c)

    def __wbg_getContext_dfc91ab0837db1d1(index, *_):
        obj = get(index)
        return add_to_stack(obj)

    add_import_func(TYPE1, __wbg_getContext_dfc91ab0837db1d1)

    def __wbg_toDataURL_97b108dd1a4b7454(offset, _):
        data_url_ = parse(data_url)

        set_int32(offset + 4, size)
        set_int32(offset, data_url_)

    add_import_func(TYPE2, __wbg_toDataURL_97b108dd1a4b7454)

    def __wbg_style_ca229e3326b3c3fb(index):
        obj = get(index)
        return add_to_stack(obj)

    add_import_func(TYPE3, __wbg_style_ca229e3326b3c3fb)

    def __wbg_instanceof_HtmlImageElement_9c82d4e3651a8533(*_):
        return True

    add_import_func(TYPE3, __wbg_instanceof_HtmlImageElement_9c82d4e3651a8533)

    def __wbg_src_87a0e38af6229364(offset, index):
        image = get(index)
        src = parse(image.src)

        set_int32(offset + 4, size)
        set_int32(offset, src)

    add_import_func(TYPE2, __wbg_src_87a0e38af6229364)

    def __wbg_width_e1a38bdd483e1283(index):
        image = get(index)
        return image.width

    add_import_func(TYPE3, __wbg_width_e1a38bdd483e1283)

    def __wbg_height_e4cc2294187313c9(index):
        image = get(index)
        return image.height

    add_import_func(TYPE3, __wbg_height_e4cc2294187313c9)

    def __wbg_complete_1162c2697406af11(index):
        image = get(index)
        return image.complete

    add_import_func(TYPE3, __wbg_complete_1162c2697406af11)

    def __wbg_data_d34dc554f90b8652(offset, index):
        imagedata = get(index)
        data = write_png(imagedata.data)

        set_int32(offset + 4, size)
        set_int32(offset, data)

    add_import_func(TYPE2, __wbg_data_d34dc554f90b8652)

    def __wbg_origin_305402044aa148ce(offset, index):
        location = get(index)
        origin = parse(location.origin)

        set_int32(offset + 4, size)
        set_int32(offset, origin)

    add_import_func(TYPE2, __wbg_origin_305402044aa148ce)

    def __wbg_length_8a9352f7b7360c37(index):
        nodelist = get(index)
        return nodelist.length

    add_import_func(TYPE3, __wbg_length_8a9352f7b7360c37)

    def __wbg_get_c30ae0782d86747f(index, _):
        nodelist = get(index)
        return add_to_stack(nodelist.image)

    add_import_func(TYPE0, __wbg_get_c30ae0782d86747f)

    def __wbg_timeOrigin_f462952854d802ec(index):
        performance = get(index)
        return float(performance.timeOrigin)

    add_import_func(TYPE19, __wbg_timeOrigin_f462952854d802ec)

    def __wbg_instanceof_Window_cee7a886d55e7df5(*_):
        return True

    add_import_func(TYPE3, __wbg_instanceof_Window_cee7a886d55e7df5)

    def __wbg_document_eb7fd66bde3ee213(index):
        fakewindow = get(index)
        return add_to_stack(fakewindow.document)

    add_import_func(TYPE3, __wbg_document_eb7fd66bde3ee213)

    def __wbg_location_b17760ac7977a47a(index):
        fakewindow = get(index)
        return add_to_stack(fakewindow.location)

    add_import_func(TYPE3, __wbg_location_b17760ac7977a47a)

    def __wbg_localStorage_3d538af21ea07fcc(*_):
        return add_to_stack(fake_window.localStorage)

    add_import_func(TYPE3, __wbg_localStorage_3d538af21ea07fcc)

    def __wbg_performance_4ca1873776fdb3d2(index):
        fakewindow = get(index)
        return add_to_stack(fakewindow.performance)

    add_import_func(TYPE3, __wbg_performance_4ca1873776fdb3d2)

    def __wbg_origin_e1f8acdeb3a39a2b(offset, index):
        fakewindow = get(index)
        origin = parse(fakewindow.origin)

        set_int32(offset + 4, size)
        set_int32(offset, origin)

    add_import_func(TYPE2, __wbg_origin_e1f8acdeb3a39a2b)

    def __wbg_get_8986951b1ee310e0(index, decode_index, decode_offset):
        fakewindow = get(index)
        attr = decode_sub(decode_index, decode_offset)

        data = getattr(fakewindow, attr)
        res = 0 if is_null(data) else add_to_stack(data)

        return res

    add_import_func(TYPE1, __wbg_get_8986951b1ee310e0)

    def __wbg_setTimeout_6ed7182ebad5d297(*_):
        return 7

    add_import_func(TYPE1, __wbg_setTimeout_6ed7182ebad5d297)

    def __wbindgen_is_object(index):
        obj = get(index)
        return obj is not None

    add_import_func(TYPE3, __wbindgen_is_object)

    def __wbg_crypto_1d1f22824a6a080c(index):
        fakewindow = get(index)
        return add_to_stack(fakewindow.crypto)

    add_import_func(TYPE3, __wbg_crypto_1d1f22824a6a080c)

    def __wbg_process_4a72847cc503995b(*_):
        return add_to_stack(None)

    add_import_func(TYPE3, __wbg_process_4a72847cc503995b)

    def __wbg_versions_f686565e586dd935(*_):
        return add_to_stack(None)

    add_import_func(TYPE3, __wbg_versions_f686565e586dd935)

    def __wbg_node_104a2ff8d6ea03a2(*_):
        return add_to_stack(None)

    add_import_func(TYPE3, __wbg_node_104a2ff8d6ea03a2)

    def __wbindgen_is_string(index):
        obj = get(index)
        return isinstance(obj, str)

    add_import_func(TYPE3, __wbindgen_is_string)

    def __wbg_require_cca90b1a94a0255b():
        pass

    add_import_func(TYPE8, __wbg_require_cca90b1a94a0255b)

    def __wbg_msCrypto_eb05e62b530a1508(index):
        fakewindow = get(index)
        return add_to_stack(fakewindow.msCrypto)

    add_import_func(TYPE3, __wbg_msCrypto_eb05e62b530a1508)

    def __wbg_randomFillSync_5c9c955aa56b6049():
        pass

    add_import_func(TYPE2, __wbg_randomFillSync_5c9c955aa56b6049)

    def __wbg_getRandomValues_3aa56aa6edec874c(*_):
        pass

    add_import_func(TYPE2, __wbg_getRandomValues_3aa56aa6edec874c)

    def __wbindgen_is_function(index):
        obj = get(index)
        return callable(obj)

    add_import_func(TYPE3, __wbindgen_is_function)

    def __wbg_self_05040bd9523805b9():
        return add_to_stack(fake_window)

    add_import_func(TYPE8, __wbg_self_05040bd9523805b9)

    def __wbg_window_adc720039f2cb14f():
        return add_to_stack(fake_window)

    add_import_func(TYPE8, __wbg_window_adc720039f2cb14f)

    def __wbg_globalThis_622105db80c1457d():
        return add_to_stack(fake_window)

    add_import_func(TYPE8, __wbg_globalThis_622105db80c1457d)

    def __wbg_global_f56b013ed9bcf359():
        return add_to_stack(fake_window)

    add_import_func(TYPE8, __wbg_global_f56b013ed9bcf359)

    def __wbg_newnoargs_cfecb3965268594c(*_):
        return 0

    add_import_func(TYPE0, __wbg_newnoargs_cfecb3965268594c)

    def __wbindgen_object_clone_ref(index):
        obj = get(index)
        return add_to_stack(obj)

    add_import_func(TYPE3, __wbindgen_object_clone_ref)

    def __wbg_eval_c824e170787ad184(index, offset):
        fake_str = f"fake_{decode_sub(index, offset)}"

        try:
            if "fake_window.pid" in fake_str:
                pid = fake_str.split("=")[1].replace("'", "").strip()

                setattr(fake_window, "pid", pid)
                eval_result = pid

            else:
                eval_result = eval(fake_str)

        except AttributeError:
            eval_result = None

        return add_to_stack(eval_result)

    add_import_func(TYPE0, __wbg_eval_c824e170787ad184)

    def __wbg_call_3f093dd26d5569f8(*_):
        return 0

    add_import_func(TYPE0, __wbg_call_3f093dd26d5569f8)

    def __wbg_call_67f2111acd2dfdb6():
        pass

    add_import_func(TYPE1, __wbg_call_67f2111acd2dfdb6)

    def __wbg_toString_6eb7c1f755c00453(_):
        return add_to_stack("[object Storage]")

    add_import_func(TYPE3, __wbg_toString_6eb7c1f755c00453)

    def __wbg_set_961700853a212a39(obj_index, key_index, value_index):
        try:
            setattr(get(obj_index), get(key_index), get(value_index))
            return True

        except AttributeError:
            return False

    add_import_func(TYPE1, __wbg_set_961700853a212a39)

    def __wbg_buffer_b914fb8b50ebbc3e(index):
        memory = get(index)
        return add_to_stack(memory.read(store))

    add_import_func(TYPE3, __wbg_buffer_b914fb8b50ebbc3e)

    def __wbg_toString_139023ab33acec36(index):
        obj = get(index)
        return add_to_stack(obj)

    add_import_func(TYPE3, __wbg_toString_139023ab33acec36)

    def __wbg_newwithbyteoffsetandlength_0de9ee56e9f6ee6e(index, offset, length):
        offset &= 0xFFFFFFFF
        length &= 0xFFFFFFFF

        buffer = get(index)
        slice = buffer[offset : offset + length]

        return add_to_stack(slice)

    add_import_func(TYPE1, __wbg_newwithbyteoffsetandlength_0de9ee56e9f6ee6e)

    def __wbg_new_b1f2d6842d615181(index):
        buffer = get(index)
        return add_to_stack(bytearray(buffer))

    add_import_func(TYPE3, __wbg_new_b1f2d6842d615181)

    def __wbg_newwithlength_0d03cef43b68a530(length):
        return add_to_stack(bytearray(length & 0xFFFFFFFF))

    add_import_func(TYPE3, __wbg_newwithlength_0d03cef43b68a530)

    def __wbg_buffer_67e624f5a0ab2319(index):
        buffer = get(index)
        return add_to_stack(buffer)

    add_import_func(TYPE3, __wbg_buffer_67e624f5a0ab2319)

    def __wbg_subarray_adc418253d76e2f1(index, num1, num2):
        buffer = get(index)
        return add_to_stack(bytearray(buffer[num1 & 0xFFFFFFFF : num2 & 0xFFFFFFFF]))

    add_import_func(TYPE1, __wbg_subarray_adc418253d76e2f1)

    def __wbg_length_21c4b0ae73cba59d(index):
        buffer = get(index)
        return len(buffer)

    add_import_func(TYPE3, __wbg_length_21c4b0ae73cba59d)

    def __wbg_set_7d988c98e6ced92d(index, index2, value):
        offset = value & 0xFFFFFFFF

        buffer = get(index)
        buffer2 = get(index2)

        buffer[offset : offset + len(buffer2)] = buffer2

    add_import_func(TYPE4, __wbg_set_7d988c98e6ced92d)

    def __wbindgen_throw():
        pass

    add_import_func(TYPE2, __wbindgen_throw)

    def __wbindgen_memory():
        return add_to_stack(wasm.exports(store)["memory"])

    add_import_func(TYPE8, __wbindgen_memory)

    def __wbindgen_closure_wrapper117(Qn, QT, *_):
        return add_to_stack(args(Qn, QT, 2, export3))

    add_import_func(TYPE1, __wbindgen_closure_wrapper117)

    def __wbindgen_closure_wrapper119(Qn, QT, *_):
        return add_to_stack(args(Qn, QT, 2, export4))

    add_import_func(TYPE1, __wbindgen_closure_wrapper119)

    def __wbindgen_closure_wrapper121(*_):
        return 0

    add_import_func(TYPE1, __wbindgen_closure_wrapper121)

    def __wbindgen_closure_wrapper123(*_):
        return 0

    add_import_func(TYPE1, __wbindgen_closure_wrapper123)

    return linker


def assign_wasm(wasm_instance: Instance) -> None:
    global wasm, wasm_memory

    wasm = wasm_instance
    wasm_memory = wasm.exports(store)["memory"]  # type: ignore


def create_wasm_instance(wasm: str | bytes, imports: Linker) -> Instance:
    if isinstance(wasm, str):
        module = Module.from_file(engine, wasm)
        instance = imports.instantiate(store, module)

        with open(wasm, "rb") as f:
            wasm_content = f.read()

        setattr(instance, "bytes", wasm_content)

    else:
        module = Module(engine, wasm)
        instance = imports.instantiate(store, module)
        setattr(instance, "bytes", wasm)

    return instance


class WasmLoader:
    def __init__(self, url: str | None = None, path: str | None = None) -> None:
        self.url = url
        self.path = path
        self.imports = load_wasm_imports()

    async def load_from_url(self) -> bytearray:
        if not self.url:
            raise ValueError("no url for wasm module provided")

        headers = {
            "Referer": fake_window.location.href,
            "Host": "megacloud.tv",
        }
        b_resp = await make_request(self.url, headers, {"v": "0.0.9"}, lambda i: i.read())
        instance = create_wasm_instance(b_resp, self.imports)

        assign_wasm(instance)

        return bytearray(instance.bytes)  # type: ignore

    async def load_from_file(self) -> bytearray:
        if not self.path:
            raise ValueError("no path for wasm module provided")

        instance = create_wasm_instance(self.path, self.imports)
        assign_wasm(instance)

        return bytearray(instance.bytes)  # type: ignore

    def groot(self) -> None:
        wasm.exports(store)["groot"](store)  # type: ignore


async def run_wasm(a: Literal["url", "file"]) -> bytes:
    if a == "url":
        wl = WasmLoader("https://megacloud.tv/images/loading.png")
        wasm_bytes = await wl.load_from_url()

    else:
        wl = WasmLoader(path=f"{os.getenv('HOME')}/wabt/bin/loading_nolog.wat")
        wasm_bytes = await wl.load_from_file()

    setattr(fake_window, "bytes", wasm_bytes)

    wl.groot()
    fake_window.jwt_plugin(wasm_bytes)
    return fake_window.navigate()


async def get_meta(url) -> None:
    headers = {
        "User-Agent": user_agent,
        "Referer": "https://hianime.to/",
    }

    html_resp = await make_request(url, headers, {}, lambda i: i.text())
    pattern = r"name=\"j_crt\" content=\"([A-Za-z0-9]+)"

    if not (match := re.search(pattern, html_resp)):
        raise ValueError("no key found")

    meta.content = match.group(1) + "=="


def split_int32(value: int) -> list[int]:
    return [
        (0xFF000000 & value) >> 24,
        (0x00FF0000 & value) >> 16,
        (0x0000FF00 & value) >> 8,
        0x000000FF & value,
    ]


def apply_xor(a, P) -> list | None:
    try:
        for indx, item in enumerate(a):
            a[indx] = item ^ P[indx % len(P)]

    except Exception:
        return None


def derive_key_and_iv(password: bytes) -> tuple[bytes, bytes]:
    hashes = []
    digest = password

    for _ in range(3):
        hash = hashlib.md5(digest).digest()
        hashes.append(hash)
        digest = hash + password

    return hashes[0] + hashes[1], hashes[2]


def decrypt_sources(password: bytes, value: str) -> str:
    bs = AES.block_size
    encrypted = base64.b64decode(value)

    salt = encrypted[8:bs]
    data = encrypted[bs:]

    key, iv = derive_key_and_iv(password + salt)

    obj = AES.new(key, AES.MODE_CBC, iv)
    result = obj.decrypt(data)

    return unpad(result, AES.block_size).decode()


async def extract(xrax: str) -> dict:
    base_url = "https://megacloud.tv"
    embed_url = f"{base_url}/embed-2/e-1/{xrax}?k=1"
    src_url = f"{base_url}/embed-2/ajax/e-1/getSources"

    # get necessary values
    canvas.baseUrl = embed_url

    fake_window.origin = base_url
    fake_window.location.href = embed_url
    fake_window.location.origin = base_url
    fake_window.xrax = xrax
    fake_window.G = xrax

    node_list.image.src = f"{base_url}/images/image.png?v=0.1.0"
    image_data.data = await get_pixel_arr(node_list.image.src)

    await get_meta(embed_url)
    q5 = await run_wasm("url")

    params = {
        "id": fake_window.pid,
        "v": fake_window.localStorage.kversion,
        "h": fake_window.localStorage.kid,
        "b": fake_window.browser_version,
    }

    headers = {
        "User-Agent": user_agent,
    }

    resp = await make_request(src_url, headers, params, lambda i: i.json())

    # decrypt
    q3 = int(fake_window.localStorage.kversion)
    q1 = split_int32(q3)
    q5 = bytearray(q5)
    q8: bytearray

    if resp["t"] != 0:
        apply_xor(q5, q1)
        q8 = q5

    else:
        q8 = resp["k"]
        apply_xor(q8, q1)

    password = base64.b64encode(q8)

    sources = json.loads(decrypt_sources(password, resp["sources"]))
    resp["sources"] = sources

    return resp
