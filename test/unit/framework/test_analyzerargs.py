import pytest

from nodescraper.models import AnalyzerArgs


class MyArgs(AnalyzerArgs):
    args_foo: int

    @classmethod
    def build_from_model(cls, datamodel):
        return cls(args_foo=datamodel.foo)


def test_build_from_model(dummy_data_model):
    dummy = dummy_data_model(foo=1)
    args = MyArgs.build_from_model(dummy)
    assert isinstance(args, MyArgs)
    assert args.args_foo == dummy.foo
    dump = args.model_dump(mode="json", exclude_none=True)
    assert dump == {"args_foo": 1}


def test_base_build_from_model_not_implemented():
    with pytest.raises(NotImplementedError):
        AnalyzerArgs.build_from_model("anything")
