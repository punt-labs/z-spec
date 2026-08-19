"""Contracts the shipped command prompts must satisfy.

`plugin/commands/*.md` is the largest surface this project ships and, until now, the
only untested one: `make check` gated the Python and the Z corpus, while
`check-dev-commands` verified that each `-dev` twin *matched* its prod source.
Two identical copies of a wrong protocol satisfy that gate perfectly — it tests
synchronisation, not correctness.

A prompt is executed by a model, so most of its content cannot be asserted
deterministically. What can be asserted is *internal consistency*: a prompt that
both specifies a wire protocol and embeds a reference implementation of it must
not contradict itself. That is the class of defect these tests cover, and it is
the class that produced the oracle verdict-envelope bug.

Every case here examines something. A parametrised case whose body loops over a
fence the file may not contain evaluates nothing and still prints a green dot,
which is how this suite once reported 48 passes while covering one command. Two
devices keep that out. Each case takes a *fenced block* as its parameter rather
than a file, so there is always a body to assert against; and
`JSON_EXAMPLE_PROMPTS` names the files the JSON contract claims to cover, so a
prompt that loses its example fails the population case instead of quietly
dropping out of the run. A test that disappears must not be indistinguishable
from a test that passes.

The population assertion is only as good as the discovery that feeds it. An
untagged fence is invisible to a tag-keyed search, so a JSON example written
without its ` ```json ` tag would be excluded from the population *and* from the
parse contract, with nothing red to show for it — the same defect arriving
through the data instead of the parametrisation. The untagged-fence case closes
that door, which is why it lives here rather than with the wider corpus
contracts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast, final

import pytest

_ROOT = Path(__file__).resolve().parents[2]
# The prompts live inside the shippable plugin/ directory, which is what the
# marketplace installs; docs/prd stays at the repo root, which it does not.
PLUGIN = _ROOT / "plugin"
COMMANDS = PLUGIN / "commands"
DOCS_PRD = _ROOT / "docs" / "prd"

# The tag group is `\w*`, not `\w+`: an untagged fence is a fence, and a pattern
# that cannot match one mis-pairs the fences on either side of it.
_FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
_JSON_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)
# Schema blocks use <angle-bracket> placeholders where a concrete example would
# carry a literal. Substituting a string keeps the block parseable, so a
# template and a worked example can be checked by the same assertions — the
# structural keys under test are literals in both. Quoted placeholders are
# replaced first; substituting the bare form inside its own quotes would
# otherwise produce `""?""`.
_QUOTED_PLACEHOLDER = re.compile(r'"<[^<>]*>"')
_BARE_PLACEHOLDER = re.compile(r"<[^<>\s][^<>]*>")


@final
@dataclass(frozen=True, slots=True)
class FencedBlock:
    """One fenced block of a prompt, with the language tag it declared."""

    source: str  # the file it came from — carried so failures name it
    index: int  # position among that file's fences
    tag: str  # "" when the fence declared no language
    body: str

    @property
    def label(self) -> str:
        """Return the test id — file and position identify a fence uniquely."""
        return f"{self.source}#{self.index}"

    def json_objects(self) -> tuple[dict[str, object], ...]:
        """Parse this block into the JSON objects it declares.

        Two forms appear in the prompts and both are legitimate: a single
        pretty-printed document (audit, partition) and an NDJSON transcript with
        one object per line (the oracle wire protocol). Try the whole block
        first, then fall back to line-by-line. `//` comments annotate the
        examples throughout and are stripped, since JSON does not permit them.

        Raise `json.JSONDecodeError` on a malformed block: a malformed example
        teaches the model a malformed format, and that is the failure this
        wants.
        """
        text = _JSON_COMMENT.sub("", self.body)
        text = _QUOTED_PLACEHOLDER.sub('"?"', text)
        text = _BARE_PLACEHOLDER.sub('"?"', text).strip()
        if not text:
            return ()

        try:
            document: object = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            return (
                (cast("dict[str, object]", document),)
                if isinstance(document, dict)
                else ()
            )

        objects: list[dict[str, object]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parsed: object = json.loads(stripped)
            if isinstance(parsed, dict):
                objects.append(cast("dict[str, object]", parsed))
        return tuple(objects)

    def holds_json(self) -> bool:
        """Whether the body is a JSON example, whatever tag the fence declared."""
        try:
            return bool(self.json_objects())
        except json.JSONDecodeError:
            return False


@final
@dataclass(frozen=True, slots=True)
class PromptDocument:
    """A shipped prompt file, addressed by the fenced blocks it declares."""

    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def blocks(self) -> tuple[FencedBlock, ...]:
        fences = cast("list[tuple[str, str]]", _FENCE.findall(self.path.read_text()))
        return tuple(
            FencedBlock(self.name, index, tag, body)
            for index, (tag, body) in enumerate(fences)
        )

    def tagged(self, lang: str) -> tuple[FencedBlock, ...]:
        return tuple(block for block in self.blocks() if block.tag == lang)

    def untagged(self) -> tuple[FencedBlock, ...]:
        return tuple(block for block in self.blocks() if not block.tag)

    def oracle_outputs(self) -> tuple[dict[str, object], ...]:
        """Return the oracle→harness lines: all but the harness→oracle commands."""
        return tuple(
            obj
            for block in self.tagged("json")
            for obj in block.json_objects()
            if "op" not in obj
        )


@final
@dataclass(frozen=True, slots=True)
class PromptCorpus:
    """The directory of shipped prompts, and the fences inside all of them."""

    root: Path

    def documents(self) -> tuple[PromptDocument, ...]:
        return tuple(PromptDocument(path) for path in sorted(self.root.glob("*.md")))

    def json_blocks(self) -> tuple[FencedBlock, ...]:
        return tuple(block for doc in self.documents() for block in doc.tagged("json"))

    def untagged_blocks(self) -> tuple[FencedBlock, ...]:
        return tuple(block for doc in self.documents() for block in doc.untagged())

    def prompts_with_json_examples(self) -> frozenset[str]:
        return frozenset(doc.name for doc in self.documents() if doc.tagged("json"))


_CORPUS = PromptCorpus(COMMANDS)

# The prod prompts the JSON contract claims to cover. Their `-dev` twins are
# added below when the tree is in dev state, because they exist only there:
# `scripts/release-plugin.sh` deletes every twin to publish, and the commit the
# release tag points at therefore has none. Naming them unconditionally made
# the suite unrunnable on exactly that commit — v0.18.0's tree failed its own
# tests — while `restore-dev-plugin.sh` put them back one commit later.
_JSON_EXAMPLE_PROD: frozenset[str] = frozenset(
    {"audit.md", "oracle.md", "partition.md"}
)


def _tree_is_dev() -> bool:
    """Return whether this checkout carries the dev plugin, twins and all.

    The manifest names the state rather than the file listing, so a tree that
    declares dev and has lost its twins fails the population check instead of
    quietly reducing what the suite examines.
    """
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    return bool(manifest["name"].endswith("-dev"))


def _expected_json_example_prompts() -> frozenset[str]:
    """Return the prompts that must carry a JSON example in this tree."""
    if not _tree_is_dev():
        return _JSON_EXAMPLE_PROD
    return _JSON_EXAMPLE_PROD | frozenset(
        f"{name.removesuffix('.md')}-dev.md" for name in _JSON_EXAMPLE_PROD
    )


JSON_EXAMPLE_PROMPTS: frozenset[str] = _expected_json_example_prompts()


# --- the JSON contract, and the population it claims --------------------------


def test_json_example_population_is_the_declared_set() -> None:
    """The suite's coverage claim must track the tree, in both directions.

    Narrowing the parametrisation to the prompts with a JSON example is what
    stops the empty cases; naming the population is what stops the narrowing
    from hiding a loss. A prompt that drops its example fails here rather than
    shrinking the run, and a prompt that gains one has to be declared before it
    counts.
    """
    found = _CORPUS.prompts_with_json_examples()
    assert found == JSON_EXAMPLE_PROMPTS, (
        f"lost its JSON example: {sorted(JSON_EXAMPLE_PROMPTS - found)}; "
        f"undeclared JSON example: {sorted(found - JSON_EXAMPLE_PROMPTS)}"
    )


@pytest.mark.parametrize("block", _CORPUS.json_blocks(), ids=lambda b: b.label)
def test_json_example_parses(block: FencedBlock) -> None:
    """A malformed example teaches the model a malformed format.

    Malformation raises out of `json_objects`; the assertion covers the other
    way an example can say nothing, which is by declaring no object at all.
    """
    assert block.json_objects(), f"{block.label}: JSON fence declares no object"


@pytest.mark.parametrize("block", _CORPUS.untagged_blocks(), ids=lambda b: b.label)
def test_untagged_fence_holds_no_json_example(block: FencedBlock) -> None:
    """A JSON example in an untagged fence is an example nothing checks.

    Every contract above is keyed on the ` ```json ` tag, so an untagged fence
    is outside all of them — including the population case, which would then
    report full coverage of a set computed without it.
    """
    assert not block.holds_json(), (
        f"{block.label}: untagged fence holds a JSON example — tag it `json` so "
        "the contract can see it"
    )


# --- the oracle protocol must distinguish a rejection from a no-op success ----


def _oracle_protocol_sources() -> list[PromptDocument]:
    """Return every document stating the oracle wire protocol in this tree.

    The `-dev` twin is included only in a dev checkout: a released tree has
    none, and naming it unconditionally makes the suite unrunnable on the
    commit the release tag points at.
    """
    sources = [PromptDocument(COMMANDS / "oracle.md")]
    if _tree_is_dev():
        sources.append(PromptDocument(COMMANDS / "oracle-dev.md"))
    sources.append(PromptDocument(DOCS_PRD / "z-oracle.md"))
    return sources


@pytest.mark.parametrize("doc", _oracle_protocol_sources(), ids=lambda d: d.name)
def test_oracle_output_carries_a_verdict(doc: PromptDocument) -> None:
    """Every oracle→harness example must say whether the operation was accepted.

    Without a verdict the wire is ambiguous: an operation rejected for violating
    its precondition and an operation that succeeded while changing nothing emit
    byte-identical lines. A property-based driver comparing traces then cannot
    assert the one property the oracle exists to establish — that the
    implementation rejects exactly what the specification rejects.
    """
    outputs = doc.oracle_outputs()
    assert outputs, f"{doc.name} defines no oracle output examples"
    for obj in outputs:
        assert "ok" in obj, f"{doc.name}: oracle output {obj} carries no verdict"
        assert "state" in obj, f"{doc.name}: oracle output {obj} has no state envelope"


@pytest.mark.parametrize("doc", _oracle_protocol_sources(), ids=lambda d: d.name)
def test_oracle_rejection_example_names_the_failed_precondition(
    doc: PromptDocument,
) -> None:
    """A driver that only learns *that* a step was rejected cannot report why."""
    rejections = [obj for obj in doc.oracle_outputs() if obj.get("ok") is False]
    assert rejections, f"{doc.name} shows no rejected-operation example"
    for obj in rejections:
        assert obj.get("reason"), f"{doc.name}: rejection {obj} gives no reason"
