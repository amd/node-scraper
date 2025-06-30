import pytest

from nodescraper.interfaces.analyzerargs import AnalyzerArgs


class MyArgs(AnalyzerArgs):
    @classmethod
    def build_from_model(cls, datamodel):
        return cls(data_model=datamodel)


def test_build_from_model(dummy_data_model):
    dummy = dummy_data_model(foo=1)
    args = MyArgs.build_from_model(dummy)
    assert isinstance(args, MyArgs)
    assert args.data_model == dummy

    a2 = MyArgs()
    dumped = a2.model_dump()  # noqa: F841
    # assert "data_model" not in dumped

    json_str = a2.model_dump_json()  # noqa: F841
    # assert '"data_model"' not in json_str


def test_base_build_from_model_not_implemented():
    with pytest.raises(NotImplementedError):
        AnalyzerArgs.build_from_model("anything")


def test_cannot_instantiate_subclass_without_build_from_model():
    with pytest.raises(TypeError):

        class BadArgs(AnalyzerArgs):
            pass

        BadArgs(data_model=None)
