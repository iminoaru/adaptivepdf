"""
Code block detection rule.

Strategy:
  - Block is entirely in a monospace font → fenced code block
  - Future: detect inline code spans within paragraphs
"""
from pdx.converter.extractor import Block
from pdx.converter.rules.base import Rule


class CodeRule(Rule):
    def applies(self, block: Block, context: dict) -> bool:
        return block.is_monospace and bool(block.text)

    def convert(self, block: Block, context: dict) -> str:
        return f"```\n{block.text}\n```"
