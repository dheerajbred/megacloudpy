import asyncio
import json
import os
import re
from time import time
from typing import Any, Literal

import aiohttp
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

from wasm_png import data_url, decoded_png

# wasm
engine = Engine()
store = Store(engine)
wasm: Instance
memory_buffer: bytearray
wasm_memory: Memory

# other
arr = [None] * 128
pointer = len(arr)
size: int
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4692.71 Safari/537.36"
date_now = int(time() * 1000)


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

        else:
            print(f"{indent}{prop}: {val[:40] if type(val).__name__ in ('list', 'bytearray') else val}")


class Meta:
    content: str


class ImageData:
    height = 50
    width = 65
    data = decoded_png


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
    z = lambda a: [
        (4278190080 & a) >> 24,
        (16711680 & a) >> 16,
        (65280 & a) >> 8,
        255 & a,
    ]
    crypto = {}
    msCrypto = {}
    browser_version = 1878522368


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
    return wasm.exports(store)["memory"]


def write_to_memory(data, offset: int) -> None:
    buffer = get_memory_buffer()

    if isinstance(data, bytes) or isinstance(data, bytearray):
        buffer[offset : offset + len(data)] = data

    elif isinstance(data, int):
        buffer[offset] = data

    else:
        raise ValueError(f"can't write '{type(data).__name__}' type")

    wasm_memory.write(store, buffer)


def set_float64(offset: int, value: int, little_endian: bool = True) -> None:
    write_to_memory(value.to_bytes(8, "little" if little_endian else "big"), offset)


def set_int32(offset: int, value: int, little_endian: bool = True) -> None:
    write_to_memory(value.to_bytes(4, "little" if little_endian else "big"), offset)


async def make_request(
    url: str,
    headers: dict,
    params: dict,
    func,
):
    async with aiohttp.ClientSession() as client:
        async with client.get(url, headers=headers, params=params) as resp:
            print(resp.url)
            return await func(resp)


def is_null(a):
    return a is None


def get(index: int) -> Any:
    return arr[index]


def parse(text: str) -> int:
    global size

    text_len = len(text)
    parsed_len = export0(text_len, 1)
    i = 0

    for char in text:
        char_code = ord(char)

        if char_code > 127:
            break

        offset = parsed_len + i

        write_to_memory(char_code, offset)
        i += 1

    size = i

    return parsed_len


def get_memory_buffer() -> bytearray:
    return wasm_memory.read(store)


def shift(index: int) -> None:
    global arr, pointer

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


def add_to_stack(item) -> int:
    global arr, pointer

    if pointer == len(arr):
        arr.append(len(arr) + 1)

    Qn = pointer
    pointer = get(Qn)
    arr[Qn] = item

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
    drop_indexes = []

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
        print("__wbindgen_is_undefined")
        res = get(index) is None
        return res

    add_import_func(TYPE3, __wbindgen_is_undefined)

    def __wbindgen_is_null(index):
        print("__wbindgen_is_null")
        a = get(index) is None
        return False

    add_import_func(TYPE3, __wbindgen_is_null)

    def __wbindgen_string_get(offset, index):
        print("__wbindgen_string_get")
        string = get(index)
        val = parse(string)

        set_int32(offset + 4, size, True)
        set_int32(offset, val, True)

    add_import_func(TYPE2, __wbindgen_string_get)

    def __wbindgen_object_drop_ref(index):
        print("__wbindgen_object_drop_ref")
        shift_get(index)

    add_import_func(TYPE5, __wbindgen_object_drop_ref)

    def __wbindgen_cb_drop(index):
        print("__wbindgen_cb_drop")
        org = shift_get(index).original
        org["cnt"] -= 1

        if org["cnt"] == 1:
            org["a"] = 0
            return True

        return False

    add_import_func(TYPE3, __wbindgen_cb_drop)

    def __wbindgen_string_new(index, offset):
        print("__wbindgen_string_new")
        res = add_to_stack(decode_sub(index, offset))
        return res

    add_import_func(TYPE0, __wbindgen_string_new)

    def __wbindgen_boolean_get(index):
        print("__wbindgen_boolean_get")
        boolean = get(index)

        res = 1 if boolean else 0 if isinstance(boolean, bool) else 2
        return res

    add_import_func(TYPE3, __wbindgen_boolean_get)

    def __wbindgen_number_get(offset, index):
        print("__wbindgen_number_get")

        number = get(index)
        set_float64(offset + 8, 0 if is_null(number) else number, True)
        set_int32(offset, 0 if is_null(number) else 1, True)

    add_import_func(TYPE2, __wbindgen_number_get)

    def __wbg_instanceof_CanvasRenderingContext2d_4ec30ddd3f29f8f9(_):
        print("__wbg_instanceof_CanvasRenderingContext2d_4ec30ddd3f29f8f9")
        return True

    add_import_func(TYPE3, __wbg_instanceof_CanvasRenderingContext2d_4ec30ddd3f29f8f9)

    def __wbg_setfillStyle_59f426135f52910f(*_):
        print("__wbg_setfillStyle_59f426135f52910f")

    add_import_func(TYPE2, __wbg_setfillStyle_59f426135f52910f)

    def __wbg_setshadowBlur_229c56539d02f401(*_):
        print("__wbg_setshadowBlur_229c56539d02f401")

    add_import_func(TYPE15, __wbg_setshadowBlur_229c56539d02f401)

    def __wbg_setshadowColor_340d5290cdc4ae9d(*_):
        print("__wbg_setshadowColor_340d5290cdc4ae9d")

    add_import_func(TYPE4, __wbg_setshadowColor_340d5290cdc4ae9d)

    def __wbg_setfont_16d6e31e06a420a5(*_):
        print("__wbg_setfont_16d6e31e06a420a5")

    add_import_func(TYPE4, __wbg_setfont_16d6e31e06a420a5)

    def __wbg_settextBaseline_c3266d3bd4a6695c(*_):
        print("__wbg_settextBaseline_c3266d3bd4a6695c")

    add_import_func(TYPE4, __wbg_settextBaseline_c3266d3bd4a6695c)

    def __wbg_drawImage_cb13768a1bdc04bd(*_):
        print("__wbg_drawImage_cb13768a1bdc04bd")

    add_import_func(TYPE16, __wbg_drawImage_cb13768a1bdc04bd)

    def __wbg_getImageData_66269d289f37d3c7(*_):
        print("__wbg_getImageData_66269d289f37d3c7")
        res = add_to_stack(image_data)
        return res

    add_import_func(TYPE17, __wbg_getImageData_66269d289f37d3c7)

    def __wbg_rect_2fa1df87ef638738(*_):
        print("__wbg_rect_2fa1df87ef638738")

    add_import_func(TYPE11, __wbg_rect_2fa1df87ef638738)

    def __wbg_fillRect_4dd28e628381d240(*_):
        print("__wbg_fillRect_4dd28e628381d240")

    add_import_func(TYPE11, __wbg_fillRect_4dd28e628381d240)

    def __wbg_fillText_07e5da9e41652f20(*_):
        print("__wbg_fillText_07e5da9e41652f20")

    add_import_func(TYPE18, __wbg_fillText_07e5da9e41652f20)

    def __wbg_setProperty_5144ddce66bbde41(*_):
        print("__wbg_setProperty_5144ddce66bbde41")

    add_import_func(TYPE7, __wbg_setProperty_5144ddce66bbde41)

    def __wbg_createElement_03cf347ddad1c8c0(*_):
        print("__wbg_createElement_03cf347ddad1c8c0")
        res = add_to_stack(canvas)
        return res

    add_import_func(TYPE1, __wbg_createElement_03cf347ddad1c8c0)

    def __wbg_querySelector_118a0639aa1f51cd(*_):
        print("__wbg_querySelector_118a0639aa1f51cd")
        res = add_to_stack(meta)
        return res

    add_import_func(TYPE1, __wbg_querySelector_118a0639aa1f51cd)

    def __wbg_querySelectorAll_50c79cd4f7573825(*_):
        print("__wbg_querySelectorAll_50c79cd4f7573825")
        res = add_to_stack(node_list)
        return res

    add_import_func(TYPE1, __wbg_querySelectorAll_50c79cd4f7573825)

    def __wbg_getAttribute_706ae88bd37410fa(offset, *_):
        print("__wbg_getAttribute_706ae88bd37410fa")

        attr = meta.content
        todo = 0 if is_null(attr) else parse(attr)

        set_int32(offset + 4, size, True)
        set_int32(offset, todo, True)

    add_import_func(TYPE6, __wbg_getAttribute_706ae88bd37410fa)

    def __wbg_target_6795373f170fd786(index):
        print("__wbg_target_6795373f170fd786")
        res = add_to_stack(get(index).target)
        return res

    add_import_func(TYPE3, __wbg_target_6795373f170fd786)

    def __wbg_addEventListener_f984e99465a6a7f4():
        print("__wbg_addEventListener_f984e99465a6a7f4")

    add_import_func(TYPE6, __wbg_addEventListener_f984e99465a6a7f4)

    def __wbg_instanceof_HtmlCanvasElement_1e81f71f630e46bc(_):
        print("__wbg_instanceof_HtmlCanvasElement_1e81f71f630e46bc")
        return True

    add_import_func(TYPE3, __wbg_instanceof_HtmlCanvasElement_1e81f71f630e46bc)

    def __wbg_setwidth_233645b297bb3318(index, set):
        print("__wbg_setwidth_233645b297bb3318")
        get(index).width = set & 0xFFFFFFFF

    add_import_func(TYPE2, __wbg_setwidth_233645b297bb3318)

    def __wbg_setheight_fcb491cf54e3527c(index, set):
        print("__wbg_setheight_fcb491cf54e3527c")
        get(index).height = set & 0xFFFFFFFF

    add_import_func(TYPE2, __wbg_setheight_fcb491cf54e3527c)

    def __wbg_getContext_dfc91ab0837db1d1(index, *_):
        print("__wbg_getContext_dfc91ab0837db1d1")
        res = add_to_stack(get(index).context2d)
        return res

    add_import_func(TYPE1, __wbg_getContext_dfc91ab0837db1d1)

    def __wbg_toDataURL_97b108dd1a4b7454(offset, _):
        print("__wbg_toDataURL_97b108dd1a4b7454")

        data_url_ = parse(data_url)
        set_int32(offset + 4, size)
        set_int32(offset, data_url_)

    add_import_func(TYPE2, __wbg_toDataURL_97b108dd1a4b7454)

    def __wbg_style_ca229e3326b3c3fb(index):
        print("__wbg_style_ca229e3326b3c3fb")
        res = add_to_stack(get(index).style)
        return res

    add_import_func(TYPE3, __wbg_style_ca229e3326b3c3fb)

    def __wbg_instanceof_HtmlImageElement_9c82d4e3651a8533(*_):
        print("__wbg_instanceof_HtmlImageElement_9c82d4e3651a8533")
        return True

    add_import_func(TYPE3, __wbg_instanceof_HtmlImageElement_9c82d4e3651a8533)

    def __wbg_src_87a0e38af6229364(offset, index):
        print("__wbg_src_87a0e38af6229364")

        src = parse(get(index).src)
        set_int32(offset + 4, size, True)
        set_int32(offset, src, True)

    add_import_func(TYPE2, __wbg_src_87a0e38af6229364)

    def __wbg_width_e1a38bdd483e1283(index):
        print("__wbg_width_e1a38bdd483e1283")
        res = get(index).width
        return res

    add_import_func(TYPE3, __wbg_width_e1a38bdd483e1283)

    def __wbg_height_e4cc2294187313c9(index):
        print("__wbg_height_e4cc2294187313c9")
        res = get(index).height
        return res

    add_import_func(TYPE3, __wbg_height_e4cc2294187313c9)

    def __wbg_complete_1162c2697406af11(index):
        print("__wbg_complete_1162c2697406af11")
        res = get(index).complete
        return res

    add_import_func(TYPE3, __wbg_complete_1162c2697406af11)

    def __wbg_data_d34dc554f90b8652(offset, index):
        print("__wbg_data_d34dc554f90b8652")
        data = write_png(get(index).data)

        set_int32(offset + 4, size, True)
        set_int32(offset, data, True)

    add_import_func(TYPE2, __wbg_data_d34dc554f90b8652)

    def __wbg_origin_305402044aa148ce(offset, index):
        print("__wbg_origin_305402044aa148ce")

        origin = parse(get(index).origin)
        set_int32(offset + 4, size, True)
        set_int32(offset, origin, True)

    add_import_func(TYPE2, __wbg_origin_305402044aa148ce)

    def __wbg_length_8a9352f7b7360c37(index):
        print("__wbg_length_8a9352f7b7360c37")
        res = get(index).length
        return res

    add_import_func(TYPE3, __wbg_length_8a9352f7b7360c37)

    def __wbg_get_c30ae0782d86747f(index, _):
        print("__wbg_get_c30ae0782d86747f")
        image = get(index).image
        res = 0 if is_null(image) else add_to_stack(image)
        return res

    add_import_func(TYPE0, __wbg_get_c30ae0782d86747f)

    def __wbg_timeOrigin_f462952854d802ec(index):
        print("__wbg_timeOrigin_f462952854d802ec")
        return float(get(index).timeOrigin)

    add_import_func(TYPE19, __wbg_timeOrigin_f462952854d802ec)

    def __wbg_instanceof_Window_cee7a886d55e7df5(*_):
        print("__wbg_instanceof_Window_cee7a886d55e7df5")
        return True

    add_import_func(TYPE3, __wbg_instanceof_Window_cee7a886d55e7df5)

    def __wbg_document_eb7fd66bde3ee213(index):
        print("__wbg_document_eb7fd66bde3ee213")
        res = add_to_stack(get(index).document)
        return res

    add_import_func(TYPE3, __wbg_document_eb7fd66bde3ee213)

    def __wbg_location_b17760ac7977a47a(index):
        print("__wbg_location_b17760ac7977a47a")
        res = add_to_stack(get(index).location)
        return res

    add_import_func(TYPE3, __wbg_location_b17760ac7977a47a)

    def __wbg_localStorage_3d538af21ea07fcc(*_):
        print("__wbg_localStorage_3d538af21ea07fcc")
        res = add_to_stack(fake_window.localStorage)
        return res

    add_import_func(TYPE3, __wbg_localStorage_3d538af21ea07fcc)

    def __wbg_performance_4ca1873776fdb3d2(index):
        print("__wbg_performance_4ca1873776fdb3d2")
        res = add_to_stack(get(index).performance)
        return res

    add_import_func(TYPE3, __wbg_performance_4ca1873776fdb3d2)

    def __wbg_origin_e1f8acdeb3a39a2b(offset, index):
        print("__wbg_origin_e1f8acdeb3a39a2b")

        origin = parse(get(index).origin)
        set_int32(offset + 4, size, True)
        set_int32(offset, origin, True)

    add_import_func(TYPE2, __wbg_origin_e1f8acdeb3a39a2b)

    def __wbg_get_8986951b1ee310e0(index, decode_index, decode_offset):
        print("__wbg_get_8986951b1ee310e0")
        fw: FakeWindow = get(index)
        data = getattr(fw, decode_sub(decode_index, decode_offset))
        res = 0 if is_null(data) else add_to_stack(data)
        return res

    add_import_func(TYPE1, __wbg_get_8986951b1ee310e0)

    def __wbg_setTimeout_6ed7182ebad5d297(*_):
        print("__wbg_setTimeout_6ed7182ebad5d297")
        return 7

    add_import_func(TYPE1, __wbg_setTimeout_6ed7182ebad5d297)

    def __wbindgen_is_object(index):
        print("__wbindgen_is_object")
        obj = get(index)
        a = obj is not None

        return a

    add_import_func(TYPE3, __wbindgen_is_object)

    def __wbg_crypto_1d1f22824a6a080c(index):
        print("__wbg_crypto_1d1f22824a6a080c")
        res = add_to_stack(get(index).crypto)
        return res

    add_import_func(TYPE3, __wbg_crypto_1d1f22824a6a080c)

    def __wbg_process_4a72847cc503995b(*_):
        print("__wbg_process_4a72847cc503995b")
        res = add_to_stack(None)
        return res

    add_import_func(TYPE3, __wbg_process_4a72847cc503995b)

    def __wbg_versions_f686565e586dd935(*_):
        print("__wbg_versions_f686565e586dd935")
        res = add_to_stack(None)
        return res

    add_import_func(TYPE3, __wbg_versions_f686565e586dd935)

    def __wbg_node_104a2ff8d6ea03a2(*_):
        print("__wbg_node_104a2ff8d6ea03a2")
        res = add_to_stack(None)
        return res

    add_import_func(TYPE3, __wbg_node_104a2ff8d6ea03a2)

    def __wbindgen_is_string(index):
        print("__wbindgen_is_string")
        res = isinstance(get(index), str)
        return res

    add_import_func(TYPE3, __wbindgen_is_string)

    def __wbg_require_cca90b1a94a0255b():
        print("__wbg_require_cca90b1a94a0255b")

    add_import_func(TYPE8, __wbg_require_cca90b1a94a0255b)

    def __wbg_msCrypto_eb05e62b530a1508(index):
        print("__wbg_msCrypto_eb05e62b530a1508")
        res = add_to_stack(get(index).msCrypto)
        return res

    add_import_func(TYPE3, __wbg_msCrypto_eb05e62b530a1508)

    def __wbg_randomFillSync_5c9c955aa56b6049():
        print("__wbg_randomFillSync_5c9c955aa56b6049")

    add_import_func(TYPE2, __wbg_randomFillSync_5c9c955aa56b6049)

    def __wbg_getRandomValues_3aa56aa6edec874c(*_):
        print("__wbg_getRandomValues_3aa56aa6edec874c")

    add_import_func(TYPE2, __wbg_getRandomValues_3aa56aa6edec874c)

    def __wbindgen_is_function(index):
        print("__wbindgen_is_function")
        res = callable(get(index))
        return res

    add_import_func(TYPE3, __wbindgen_is_function)

    def __wbg_self_05040bd9523805b9():
        print("__wbg_self_05040bd9523805b9")
        res = add_to_stack(fake_window)
        return res

    add_import_func(TYPE8, __wbg_self_05040bd9523805b9)

    def __wbg_window_adc720039f2cb14f():
        print("__wbg_window_adc720039f2cb14f")
        res = add_to_stack(fake_window)
        return res

    add_import_func(TYPE8, __wbg_window_adc720039f2cb14f)

    def __wbg_globalThis_622105db80c1457d():
        print("__wbg_globalThis_622105db80c1457d")
        res = add_to_stack(fake_window)
        return res

    add_import_func(TYPE8, __wbg_globalThis_622105db80c1457d)

    def __wbg_global_f56b013ed9bcf359():
        print("__wbg_global_f56b013ed9bcf359")
        res = add_to_stack(fake_window)
        return res

    add_import_func(TYPE8, __wbg_global_f56b013ed9bcf359)

    def __wbg_newnoargs_cfecb3965268594c(*_):
        print("__wbg_newnoargs_cfecb3965268594c")
        return 0

    add_import_func(TYPE0, __wbg_newnoargs_cfecb3965268594c)

    def __wbindgen_object_clone_ref(index):
        print("__wbindgen_object_clone_ref")
        res = add_to_stack(get(index))
        return res

    add_import_func(TYPE3, __wbindgen_object_clone_ref)

    def __wbg_eval_c824e170787ad184(index, offset):
        print("__wbg_eval_c824e170787ad184")
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

        a = add_to_stack(eval_result)
        return a

    add_import_func(TYPE0, __wbg_eval_c824e170787ad184)

    def __wbg_call_3f093dd26d5569f8(*_):
        print("__wbg_call_3f093dd26d5569f8")
        return 0

    add_import_func(TYPE0, __wbg_call_3f093dd26d5569f8)

    def __wbg_call_67f2111acd2dfdb6():
        print("__wbg_call_67f2111acd2dfdb6")

    add_import_func(TYPE1, __wbg_call_67f2111acd2dfdb6)

    def __wbg_toString_6eb7c1f755c00453(_):
        print("__wbg_toString_6eb7c1f755c00453")
        res = add_to_stack("[object Storage]")
        return res

    add_import_func(TYPE3, __wbg_toString_6eb7c1f755c00453)

    def __wbg_set_961700853a212a39(obj_index, key_index, value_index):
        print("__wbg_set_961700853a212a39")
        try:
            setattr(get(obj_index), get(key_index), get(value_index))
            return True

        except AttributeError:
            return False

    add_import_func(TYPE1, __wbg_set_961700853a212a39)

    def __wbg_buffer_b914fb8b50ebbc3e(index):
        print("__wbg_buffer_b914fb8b50ebbc3e")
        mem: Memory = get(index)
        res = add_to_stack(mem.read(store))
        return res

    add_import_func(TYPE3, __wbg_buffer_b914fb8b50ebbc3e)

    def __wbg_toString_139023ab33acec36(index):
        print("__wbg_toString_139023ab33acec36")
        res = add_to_stack(str(get(index)))
        return res

    add_import_func(TYPE3, __wbg_toString_139023ab33acec36)

    def __wbg_newwithbyteoffsetandlength_0de9ee56e9f6ee6e(index, offset, length):
        print("__wbg_newwithbyteoffsetandlength_0de9ee56e9f6ee6e")
        mv = memoryview(get(index))
        offset &= 0xFFFFFFFF
        length &= 0xFFFFFFFF

        res = add_to_stack(bytearray(mv[offset : offset + length]))
        return res

    add_import_func(TYPE1, __wbg_newwithbyteoffsetandlength_0de9ee56e9f6ee6e)

    def __wbg_new_b1f2d6842d615181(index):
        print("__wbg_new_b1f2d6842d615181")
        res = add_to_stack(bytearray(get(index)))
        return res

    add_import_func(TYPE3, __wbg_new_b1f2d6842d615181)

    def __wbg_newwithlength_0d03cef43b68a530(length):
        print("__wbg_newwithlength_0d03cef43b68a530")
        res = add_to_stack(bytearray(length & 0xFFFFFFFF))
        return res

    add_import_func(TYPE3, __wbg_newwithlength_0d03cef43b68a530)

    def __wbg_buffer_67e624f5a0ab2319(index):
        print("__wbg_buffer_67e624f5a0ab2319")
        res = add_to_stack(get(index))
        return res

    add_import_func(TYPE3, __wbg_buffer_67e624f5a0ab2319)

    def __wbg_subarray_adc418253d76e2f1(index, num1, num2):
        print("__wbg_subarray_adc418253d76e2f1")
        res = add_to_stack(get(index)[num1 & 0xFFFFFFFF : num2 & 0xFFFFFFFF])
        return res

    add_import_func(TYPE1, __wbg_subarray_adc418253d76e2f1)

    def __wbg_length_21c4b0ae73cba59d(index):
        print("__wbg_length_21c4b0ae73cba59d")
        res = len(get(index))
        return res

    add_import_func(TYPE3, __wbg_length_21c4b0ae73cba59d)

    def __wbg_set_7d988c98e6ced92d(index, index2, value):
        global arr
        print("__wbg_set_7d988c98e6ced92d")
        offset = value & 0xFFFFFFFF

        get(index)[offset : offset + len(get(index2))] = get(index2)

    add_import_func(TYPE4, __wbg_set_7d988c98e6ced92d)

    def __wbindgen_throw():
        print("__wbindgen_throw")

    add_import_func(TYPE2, __wbindgen_throw)

    def __wbindgen_memory():
        print("__wbindgen_memory")
        res = add_to_stack(wasm.exports(store)["memory"])
        return res

    add_import_func(TYPE8, __wbindgen_memory)

    def __wbindgen_closure_wrapper117(Qn, QT, *_):
        print("__wbindgen_closure_wrapper117")
        res = add_to_stack(args(Qn, QT, 2, export3))
        return res

    add_import_func(TYPE1, __wbindgen_closure_wrapper117)

    def __wbindgen_closure_wrapper119(Qn, QT, *_):
        print("__wbindgen_closure_wrapper119")
        res = add_to_stack(args(Qn, QT, 2, export4))
        return res

    add_import_func(TYPE1, __wbindgen_closure_wrapper119)

    def __wbindgen_closure_wrapper121(Qn, QT, *_):
        print("__wbindgen_closure_wrapper121")
        res = add_to_stack(args(Qn, QT, 2, export5))
        return res

    add_import_func(TYPE1, __wbindgen_closure_wrapper121)

    def __wbindgen_closure_wrapper123(Qn, QT):
        print("__wbindgen_closure_wrapper121")
        res = add_to_stack(args(Qn, QT, 9, export4))
        return res

    add_import_func(TYPE1, __wbindgen_closure_wrapper123)

    # def __wbindgen_closure_wrapper123(value):
    #     print(f"value: {value}")
    #     return value
    #
    # add_import_func(TYPE3, __wbindgen_closure_wrapper123)

    return linker


def assign_wasm(wasm_instance: Instance) -> None:
    global wasm, memory_buffer, wasm_memory

    wasm = wasm_instance
    memory_buffer = bytearray()
    wasm_memory = wasm.exports(store)["memory"]


def QN(wasm: str | bytes, imports: Linker) -> Instance:

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
        instance = QN(b_resp, self.imports)

        assign_wasm(instance)

        return bytearray(instance.bytes)

    async def load_from_file(self) -> bytearray:
        if not self.path:
            raise ValueError("no path for wasm module provided")

        instance = QN(self.path, self.imports)
        assign_wasm(instance)

        return bytearray(instance.bytes)

    def groot(self) -> None:
        wasm.exports(store)["groot"](store)  # type: ignore


async def V(a: Literal["url", "file"]) -> None:
    if a == "url":
        wl = WasmLoader("https://megacloud.tv/images/loading.png")
        Q0 = await wl.load_from_url()

    else:
        wl = WasmLoader(path=f"{os.getenv('HOME')}/wabt/bin/loading.wat")
        Q0 = await wl.load_from_file()

    setattr(fake_window, "bytes", Q0)

    print("\ngroot()")
    wl.groot()

    print("\njwt_plugin()")
    fake_window.jwt_plugin(Q0)

    print("\nnavigate()")
    return fake_window.navigate()


async def get_meta(url) -> None:
    headers = {
        "User-Agent": user_agent,
        "Referer": "https://hianime.to/",
    }

    html_resp = await make_request(url, headers, {}, lambda i: i.text())
    pattern = r"name=\"j_crt\" content=\"([A-Za-z0-9=]+)\""

    if not (match := re.search(pattern, html_resp)):
        raise ValueError("no key found")

    meta.content = match.group(1)


async def main(xrax: str):
    embed_url = f"https://megacloud.tv/embed-2/e-1/{xrax}?k=1"
    base_url = "https://megacloud.tv"
    src_url = "https://megacloud.tv/embed-2/ajax/e-1/getSources"

    canvas.baseUrl = embed_url

    fake_window.origin = base_url
    fake_window.location.href = embed_url
    fake_window.location.origin = base_url
    fake_window.xrax = xrax
    fake_window.G = xrax

    node_list.image.src = f"{base_url}/images/image.png?v=0.1.0"

    await get_meta(embed_url)
    await V("url")

    print("\n")
    inspect_class(fake_window, 1)
    print("\n")
    inspect_class(node_list, 1)
    print("\n")
    inspect_class(canvas, 1)
    print("\n")
    inspect_class(meta, 1)
    print("\n")
    inspect_class(image_data, 1)
    print("\n")

    params = {
        "id": fake_window.pid,
        "v": fake_window.localStorage.kversion,
        "h": fake_window.localStorage.kid,
        "b": fake_window.browser_version,
    }

    # only user agent is required
    headers = {
        "User-Agent": user_agent,
    }

    resp = await make_request(src_url, headers, params, lambda i: i.json())
    print(resp)


asyncio.run(main("F4BiN3AousfB"))
