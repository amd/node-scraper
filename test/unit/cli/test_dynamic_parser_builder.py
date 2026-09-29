# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import argparse
from typing import Literal, Optional

from pydantic import BaseModel

from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.typeutils import TypeUtils


class LiteralArgsModel(BaseModel):
    mode: Literal["fast", "slow"] = "fast"
    opt_mode: Optional[Literal["on", "off"]] = None


def _action_for(parser: argparse.ArgumentParser, option: str) -> argparse.Action:
    for action in parser._actions:
        if option in action.option_strings:
            return action
    raise AssertionError(f"no action for {option}")


def test_optional_literal_field_gets_choices() -> None:
    """Baseline: Optional[Literal[...]] is rendered with argparse choices."""
    parser = argparse.ArgumentParser()
    DynamicParserBuilder(parser, object).build_model_arg_parser(LiteralArgsModel, required=False)  # type: ignore

    assert _action_for(parser, "--opt-mode").choices == ["on", "off"]


def test_plain_literal_field_gets_choices() -> None:
    """A bare Literal[...] field must also be rendered with argparse choices."""
    parser = argparse.ArgumentParser()
    DynamicParserBuilder(parser, object).build_model_arg_parser(LiteralArgsModel, required=False)  # type: ignore

    assert _action_for(parser, "--mode").choices == ["fast", "slow"]


def test_get_literal_choices_returns_literal_values() -> None:
    """get_literal_choices must return the Literal's allowed values."""
    type_classes = TypeUtils.process_type(Literal["fast", "slow"])  # type: ignore
    type_class_map = {tc.type_class: tc for tc in type_classes}

    assert DynamicParserBuilder.get_literal_choices(type_class_map) == ["fast", "slow"]
