import base64
import hashlib
import json
import time
import asyncio
from urllib import parse
import re
import aiohttp

from typing import Awaitable, Callable, TypeVar, overload, Literal
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from enum import StrEnum, IntEnum


T = TypeVar("T")


class ResolverFlags(IntEnum):
    MAP = 1 << 0
    REVERSE = 1 << 1
    FROMCHARCODE = 1 << 2
    SLICE = 1 << 3
    SPLIT = 1 << 4
    ABC = 1 << 5
    FALLBACK = 1 << 6


class Patterns(StrEnum):
    _FUNC = r"[\w$]{3}\.[\w$]{2}"
    _FUNC2 = r"[\w$]\.[\w$]{2}"
    _FUNC3 = r"[\w$]{3}\.[\w$]{3}"

    SOURCE_ID = r"embed-2/v2/e-1/([A-z0-9]+)\?"

    IDX = r'"(\d+)"'
    VAR = r'[ ;]{name}=(?:\+?"?(\d+)"?;|[\w$][\w$][\w$]\.[\w$][\w$]\(((?:"?\d+"?,?)+)\))'
    DICT = r"[\w$]{2}=\{\}"

    XOR_KEY = r"\)\('(.+)'\)};"
    STRING = r"function [\w$]{2}\(\){return \"(.+?)\";}"
    DELIMITER = r"[\w$]{3}=\w\.[\w$]{2}\([\w$]{3},'(.)'\);"

    BITWISE_SWITCHCASE = r"\w\[\d+\]=\(function\([\w$]+\)[{\d\w$:\(\),= ]+;switch\([\w$]+\){([^}]+)}"
    BITWISE_OPERATION = r"case (\d+):([\w\[\]\-+|><^* =$\(\)]+);break;"
    BITWISE_DEF_FLAG_FUNC = r"\w\[\d+\]=\(function\([\w$]+\).+?;switch\([\w$]+\){[^,]+,([\w$]+)"
    SET_DEF_FLAG = rf"{_FUNC}\((\d+)\)"

    SLICES = rf"case\s(\d{{1,2}}):{_FUNC2}\({_FUNC2}\(\),[\w$]{{3}},{_FUNC2}\({_FUNC2}\([\w$]{{3}},([\d\-]+),[\d\-]+\),[\d\-]+,([\d\-]+)\)\)"

    _GET1_INDEX = r'+?"?(\w+)"?( [|\-\+*><^]+ "?\w+"?)?'
    GET1 = rf"{_FUNC}\(\{_GET1_INDEX}\)"
    GET2 = rf'{_FUNC}\({_FUNC}\("?(\w+)"?,"?(\w+)"?\)\)'
    GET3 = rf'{_FUNC}\({_FUNC}\("?(\w+)"?,"?(\w+)"?,{SET_DEF_FLAG}\)\)'
    GET = f"({GET1}|{GET2}|{GET3})"

    INDEX_ARRAY_CONTENT = r'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    INDEX_ARRAY_ITEM = rf'({_FUNC}\([\w",\(\)]+\))|({_FUNC}\("?\d+"?,"?\d+"?,{_FUNC}\(\d+\)\))|(\d+)'

    KEY_ARRAY_CONTENT = rf'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    KEY_VAR = rf'var [\w$,]{{28,}};(?:{_FUNC}\(\+?"?\d+"?\);)?[\w$]+=([\w$.\(\)\+,"]+);'

    KEYGEN = r"var [\w$,]{28,};.+?\w=\(\)=>{(.+?)};"
    MAP = r"\((\w)=>{(.+?return.+?;)"

    PARSE_INT = r'\w+\({},\+?"16"?\)'
    BITWISE2 = rf"{_FUNC}\((\w),(\w\))"
    BITWISE3 = rf'{_FUNC}\("?(\d+)"?,"?(\d+)"?,{_FUNC}\((\d)\)\)'

    GET_KEY = r"var [\w$,]{28,};(.+?)try"
    GET_KEY_FUNC = r"(\w)=\(\)=>{(.+?)};"
    GET_KEY_FUNC_RETURN = r"\w=\(\)=>{.+?return(.+?);[\}\)]"

    DICT_SET1 = rf"[\w$]{{2}}\[(?:{GET})\]=({GET})"
    DICT_SET2 = rf"[\w$]{{2}}\[(?:{GET})\]=\(\)=>({{.+?return {GET})"
    DICT_SET = f"{DICT_SET1}|{DICT_SET2}"


class Resolvers:
    @staticmethod
    def _get_key(s: "Megacloud") -> str:
        fcall = _re(Patterns.KEY_VAR, s.script, l=False).group(1)
        args = _re(Patterns.GET, fcall, l=False).groups()

        return s._get(args[1:], fcall).replace("-", "")

    @staticmethod
    def _get_keys(s: "Megacloud") -> list[str]:
        key_array_items = _re(Patterns.KEY_ARRAY_CONTENT, s.script, l=True)[0]
        func_calls = re.split(r"(?<=\)),(?=\w)", key_array_items)

        keys = []
        for fcall in func_calls:
            args = _re(Patterns.GET, fcall, l=False).groups()
            keys.append(s._get(args[1:], ""))

        return keys

    @classmethod
    def slice(cls, s: "Megacloud") -> tuple[list, list]:
        key = cls._get_key(s)
        if key.endswith("="):
            key = base64.b64decode(key).decode()

        return list(key), list(range(0, len(key)))

    @classmethod
    def abc(cls, s: "Megacloud") -> tuple[list, list]:
        values = {}
        c = _re(Patterns.GET_KEY, s.script, l=False).group(1)

        for f in _re(Patterns.DICT_SET, c, l=True):
            i = 0 if f[0] else 17
            key_idxs = list(filter(None, f[i + 1 : i + 8]))

            context = f[i + 8]
            value_idxs = list(filter(None, f[i + 10 : i + 17]))

            k = s._get(key_idxs, c)
            v = s._get(value_idxs, context)

            values[k] = v

        get_key_func = _re(Patterns.GET_KEY_FUNC, c, l=False).group(2)

        order = get_key_func.split("return")[-1].split(";")[0]
        order = order.replace("()", "")
        order = re.sub(rf"\w\[(.+?)\]", r"\1", order)

        for f in _re(Patterns.GET, order, l=True):
            indexes = list(filter(None, f[1:]))

            v = s._get(indexes, get_key_func)
            order = order.replace(f[0], f'"{values[v]}"')

        key = eval(order)
        return list(key), list(range(0, len(key)))

    @classmethod
    def map(cls, s: "Megacloud") -> tuple[list, list]:
        try:
            keys = cls._get_keys(s)
        except ValueError as e:
            print(f"keys not found: {e}")
            keys = []

        try:
            indexes = s._get_indexes()
        except ValueError as e:
            print(f"indexes not found: {e}")
            indexes = []

        return keys, indexes

    @classmethod
    def from_charcode(cls, s: "Megacloud", keys: list = [], indexes: list = []) -> tuple[list, list]:
        raw_values = []

        if indexes:
            map_ = _re(Patterns.MAP, s.script, l=False)
            map_arg = map_.group(1)
            map_body = map_.group(2)
            if m := re.search(Patterns.BITWISE2, map_body):
                flag = _re(Patterns.SET_DEF_FLAG, map_body, l=False).group(1)
                func = s.bitwise[int(flag)]

                var_name = m.group(1) if m.group(1) != map_arg else m.group(2)
                var_value = _re(Patterns.VAR.format(name=var_name), s.script, l=False).group(1)

                raw_values = [func(int(var_value), int(i)) for i in indexes]

        elif keys:
            map_ = _re(Patterns.MAP, s.script, l=False)
            map_arg = map_.group(1)
            map_body = map_.group(2)

            if re.search(Patterns.PARSE_INT.format(map_arg), map_body):
                raw_values = [int(k, 16) for k in keys]

            # elif m := re.search(bitwise3_pattern, map_body):
            #     ...

        else:
            indexes = s._get_indexes()
            raw_values = [int(i) for i in indexes]

        return [chr(v) for v in raw_values], list(range(0, len(raw_values)))

    @classmethod
    def fallback(cls, s: "Megacloud") -> tuple[list, list]:
        to_try = [cls.slice, cls.map, cls.from_charcode]

        for t in to_try:
            try:
                return t(s)
            except ValueError:
                continue

        else:
            raise ValueError("key not found =(")

    @classmethod
    def resolve(cls, flags: int, s: "Megacloud") -> bytes:
        key = ""
        keys = []
        indexes = []

        if flags & ResolverFlags.MAP:
            keys, indexes = cls.map(s)
            print(keys, indexes)

        if flags & (ResolverFlags.SLICE | ResolverFlags.SPLIT):
            keys, indexes = cls.slice(s)

        if flags & ResolverFlags.FROMCHARCODE:
            keys, indexes = cls.from_charcode(s, keys, indexes)

        if flags & ResolverFlags.FALLBACK:
            keys, indexes = cls.fallback(s)

        if flags & ResolverFlags.ABC:
            keys, indexes = cls.abc(s)

        key = "".join(keys[i] for i in indexes)

        if flags & ResolverFlags.REVERSE:
            key = "".join(reversed(key))

        return key.encode()


async def make_request(url: str, headers: dict, params: dict, func: Callable[[aiohttp.ClientResponse], Awaitable[T]]) -> T:
    async with aiohttp.ClientSession() as client:
        async with client.get(url, headers=headers, params=params) as resp:
            return await func(resp)


@overload
def _re(pattern: Patterns | str, string: str, *, l: Literal[True]) -> list[str]: ...
@overload
def _re(pattern: Patterns | str, string: str, *, l: Literal[False]) -> re.Match: ...


def _re(pattern: Patterns | str, string: str, *, l: bool) -> re.Match | list[str]:
    if l:
        v = re.findall(pattern, string)

    else:
        v = re.search(pattern, string)

    if not v:
        msg = f"{pattern.name} not found" if isinstance(pattern, Patterns) else f"{pattern} not found"
        raise ValueError(msg)

    return v


def derive_key_and_iv(password: bytes) -> tuple[bytes, bytes]:
    hashes = []
    digest = password

    for _ in range(3):
        hash = hashlib.md5(digest).digest()
        hashes.append(hash)
        digest = hash + password

    return hashes[0] + hashes[1], hashes[2]


def decrypt_sources(key: bytes, value: str) -> str:
    bs = AES.block_size
    encrypted = base64.b64decode(value)

    salt = encrypted[8:bs]
    data = encrypted[bs:]

    key, iv = derive_key_and_iv(key + salt)

    obj = AES.new(key, AES.MODE_CBC, iv)
    result = obj.decrypt(data)

    return unpad(result, AES.block_size).decode()


def generate_sequence(n: int) -> list[int]:
    res = [5, 8, 14, 11]
    if n <= 4:
        return res

    for i in range(2, n - 2):
        res.append(res[i] + i + 3 - (i % 2))

    return res


class Megacloud:
    base_url = "https://megacloud.blog"
    headers = {
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        "origin": base_url,
        "referer": base_url,
    }

    def __init__(self, embed_url: str) -> None:
        self.embed_url = embed_url

        self.script: str
        self.string_array: list[str]
        self.bitwise: dict[int, Callable]

    def _generate_bitwise_func(self, operation: str) -> Callable:
        operation = re.sub(r"[\w$]{2}", "args", operation)
        if any(i in operation for i in (">", "<")):
            v = operation.split()
            v[-1] = f"({v[-1]} & 31)"
            operation = " ".join(v)

        return lambda *args: eval(operation)

    def _get_bitwise_operations(self) -> dict[int, Callable]:
        functions = {}

        switchcase_section = _re(Patterns.BITWISE_SWITCHCASE, self.script, l=False).group(1)
        for num, operation in _re(Patterns.BITWISE_OPERATION, switchcase_section, l=True):
            functions[int(num)] = self._generate_bitwise_func(operation.split("=")[1])

        return functions

    def _get_array_slices(self) -> list[tuple[int, ...]]:
        pairs = tuple(map(lambda t: tuple(map(int, t)), _re(Patterns.SLICES, self.script, l=True)))
        order_map = {v: i for i, v in enumerate(generate_sequence(len(pairs)))}

        pairs = list(sorted(pairs, key=lambda t: order_map[t[0]]))
        return pairs

    def _shuffle_array(self, array: list[str]) -> list[str]:
        slices = self._get_array_slices()
        for _, array_idx, tail_idx in slices:
            array, tail = array[:array_idx], array[array_idx:]
            array = tail[:tail_idx] + array

        return array

    def _get(self, values, ctx: str) -> str:
        values = list(filter(None, values))

        def get_flag() -> int:
            try:
                flag = _re(Patterns.SET_DEF_FLAG, ctx, l=False).group(1)
                flag = int(flag[0])

            except ValueError:
                flag = 0

            return flag

        if len(values) == 1 or not values[1].isdigit():
            if len(values) == 2:
                expression = values[-1].split()

                operator = expression[0]
                operand = expression[-1]

                if not operand.isdigit():
                    bitwise_args = _re(Patterns.VAR.format(name=operand), self.script, l=False).groups()
                    bitwise_args = bitwise_args[0] or bitwise_args[1]
                    bitwise_args = map(int, re.findall(r"(\d+)", bitwise_args))

                    flag = get_flag()
                    operand = str(self.bitwise[flag](*bitwise_args))

                if any(i in operator for i in (">", "<")):
                    operand = f"({operand} & 31)"

                values[-1] = f"{operator} {operand}"
                i = eval("".join(values))

            else:
                i = int(values[0])

            v = self.string_array[i]

        elif len(values) > 1:
            i1 = int(values[0])
            i2 = int(values[1])
            flag = int(values[2]) if len(values) == 3 else get_flag()

            i = self.bitwise[flag](i1, i2)
            v = self.string_array[i]

        else:
            raise ValueError(f"can't get {values}")

        return v

    def _get_indexes(self) -> list[int]:
        indexes = []
        array_items = _re(Patterns.INDEX_ARRAY_CONTENT, self.script, l=True)[-1]
        for m in _re(Patterns.INDEX_ARRAY_ITEM, array_items, l=True):
            idx = m[0] or m[1] or m[2]

            if not idx.isdigit():
                idx = _re(Patterns.IDX, idx, l=False).group(1)

            indexes.append(int(idx))

        return indexes

    def _resolve_key(self) -> bytes:
        keygen_func = _re(Patterns.KEYGEN, self.script, l=False)
        keygen_body = keygen_func.group(1)

        functions: list[str] = []
        print(keygen_body)

        for i in re.findall(Patterns.GET, keygen_body):
            functions.append(self._get(i[1:], keygen_body))

        print(functions)
        flags = 0

        for f in functions:
            if f.upper() in ResolverFlags._member_names_:
                flags |= ResolverFlags[f.upper()]

            elif len(f) == 1 and ord(f) in range(97, 123):
                flags |= ResolverFlags.ABC

        if not flags:
            flags |= ResolverFlags.FALLBACK

        key = Resolvers.resolve(flags, self) or b":P"
        return key

    async def _get_secret_key(self) -> bytes:
        strings = ""

        script_url = f"{self.base_url}/js/player/a/v2/pro/embed-1.min.js"
        script_version = int(time.time())
        self.script = await make_request(script_url, {}, {"v": script_version}, lambda i: i.text())

        xor_key = _re(Patterns.XOR_KEY, self.script, l=False).group(1)
        char_sequence = parse.unquote(_re(Patterns.STRING, self.script, l=False).group(1))
        delim = _re(Patterns.DELIMITER, self.script, l=False).group(1)

        for i in range(len(char_sequence)):
            a = ord(char_sequence[i])
            b = ord(xor_key[i % len(xor_key)])

            idx = a ^ b
            strings += chr(idx)

        string_array = strings.split(delim)
        self.string_array = self._shuffle_array(string_array)
        self.bitwise = self._get_bitwise_operations()

        key = self._resolve_key()
        return key

    async def extract(self) -> dict:
        id = _re(Patterns.SOURCE_ID, self.embed_url, l=False).group(1)
        get_src_url = f"{self.base_url}/embed-2/v2/e-1/getSources"

        resp = await make_request(get_src_url, self.headers, {"id": id}, lambda i: i.json())

        if not resp["sources"]:
            raise ValueError("no sources found")

        key = await self._get_secret_key()
        sources = json.loads(decrypt_sources(key, resp["sources"]))

        resp["sources"] = sources

        resp["intro"] = resp["intro"]["start"], resp["intro"]["end"]
        resp["outro"] = resp["outro"]["start"], resp["outro"]["end"]

        return resp


async def main():
    url = "https://megacloud.blog/embed-2/v2/e-1/HakXnbHZZUiV?k=1&autoPlay=1&oa=0&asi=1"
    a = Megacloud(url)
    print(json.dumps(await a.extract(), indent=4))


asyncio.run(main())