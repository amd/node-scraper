###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

from errorscraper.typeutils import TypeClass, TypeData, TypeUtils

T = TypeVar("T")


class TestGenericBase(Generic[T]):

    def __init__(self, generic_type: T):
        self.generic_type = generic_type

    def test_func(self, arg: list[str], arg2: bool | str, arg3: Optional[int] = None) -> T:
        return self.generic_type


class TestGenericImpl(TestGenericBase[str]):
    pass


class TestModel(BaseModel):
    str_attr: str
    int_attr: int
    list_attr: list[str]
    bool_attr: bool
    optional_attr: Optional[str] = None


def test_generic_map():
    assert TypeUtils.get_generic_map(TestGenericImpl) == {T: str}


def test_func_arg_types():
    res = TypeUtils.get_func_arg_types(TestGenericImpl.test_func, TestGenericImpl)
    assert list(res.keys()) == ["arg", "arg2", "arg3"]
    assert res["arg"] == TypeData(
        type_classes=[TypeClass(type_class=list, inner_type=str)], required=True
    )
    assert res["arg2"] == TypeData(
        type_classes=[
            TypeClass(type_class=bool, inner_type=None),
            TypeClass(type_class=str, inner_type=None),
        ],
        required=True,
    )
    assert res["arg3"] == TypeData(
        type_classes=[TypeClass(type_class=int, inner_type=None)], required=False
    )


def test_model_types():
    res = TypeUtils.get_model_types(TestModel)
    assert list(res.keys()) == ["str_attr", "int_attr", "list_attr", "bool_attr", "optional_attr"]
    assert res["str_attr"] == TypeData(
        type_classes=[TypeClass(type_class=str, inner_type=None)], required=True
    )
    assert res["int_attr"] == TypeData(
        type_classes=[TypeClass(type_class=int, inner_type=None)], required=True
    )
    assert res["list_attr"] == TypeData(
        type_classes=[TypeClass(type_class=list, inner_type=str)], required=True
    )
    assert res["bool_attr"] == TypeData(
        type_classes=[TypeClass(type_class=bool, inner_type=None)], required=True
    )
    assert res["optional_attr"] == TypeData(
        type_classes=[TypeClass(type_class=str, inner_type=None)], required=False
    )
