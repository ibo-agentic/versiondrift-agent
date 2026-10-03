"""Native chat-wrapping checks (PLAN.md 10.1 item 1 follow-up, 2026-10-03):
double-BOS avoidance, stop tokens from the model's own template, and
add_generation_prompt. Pure-logic tests only -- no GGUF/model is loaded;
the real llama-cpp-python tokenizer contract these rely on is cited by
file:line in upgradecanary/model/llama_cpp_client.py and was verified by
reading the installed package's source directly (see ENGINEERING_NOTES.md).
"""

from __future__ import annotations

import pytest

from upgradecanary.model.llama_cpp_client import (
    build_native_stop_list,
    check_context_budget,
    resolve_native_prompt_text,
)

BOS = "<s>"
BOS_ID = 1  # arbitrary stand-in id, matches common llama.cpp conventions


class _FakeTokenizer:
    """Mimics llama_cpp.Llama.tokenize's real contract well enough to test
    OUR add_bos decision, without needing a real GGUF:
    - add_bos=True prepends exactly one BOS id (verified against the
      installed package, llama.py:602-618's tokenize() / _create_completion's
      bos_tokens handling).
    - special=True recognizes special-token *text* (here, just the literal
      BOS string) wherever it occurs and maps it to the BOS id, same as
      llama.cpp's real special-token matching -- this is what lets a
      template-embedded "<s>" become exactly one BOS id without any
      separate auto-add.
    """

    def tokenize(self, text: bytes, add_bos: bool = True, special: bool = False) -> list[int]:
        s = text.decode("utf-8")
        body: list[int] = []
        if special and BOS in s:
            before, _, after = s.partition(BOS)
            body = [ord(c) % 1000 + 10 for c in before] + [BOS_ID] + [ord(c) % 1000 + 10 for c in after]
        else:
            body = [ord(c) % 1000 + 10 for c in s]
        return ([BOS_ID] if add_bos else []) + body


def test_resolve_does_not_auto_add_bos_when_template_already_embeds_it():
    rendered = f"{BOS}[INST] hello [/INST]"
    text, add_bos = resolve_native_prompt_text(rendered, BOS, model_wants_bos=True)
    # Text is left UNCHANGED -- the literal "<s>" stays in place and is
    # recognized as the BOS token during tokenization (special=True),
    # rather than being stripped and relying on an auto-add.
    assert text == rendered
    assert add_bos is False


def test_resolve_leaves_text_alone_when_template_omits_bos():
    rendered = "<|im_start|>user\nhello<|im_end|>\n<|im_start|>assistant"
    text, add_bos = resolve_native_prompt_text(rendered, BOS, model_wants_bos=True)
    assert text == rendered
    assert add_bos is True


def test_resolve_never_adds_bos_when_model_has_none():
    rendered = f"{BOS}hello"
    text, add_bos = resolve_native_prompt_text(rendered, BOS, model_wants_bos=False)
    assert add_bos is False
    # Text is left untouched in this branch -- there is nothing to strip
    # since this model never gets a BOS added either way.
    assert text == rendered


def test_resolve_treats_empty_bos_token_as_no_match():
    rendered = "hello world"
    text, add_bos = resolve_native_prompt_text(rendered, "", model_wants_bos=True)
    assert text == "hello world"
    assert add_bos is True


def test_no_double_bos_in_first_tokens_when_template_embeds_bos():
    """The actual thing PLAN.md asked to check: the FIRST tokens of a fully
    resolved (resolve + tokenize) native prompt contain exactly one BOS id,
    not two, when the chat template renders its own leading bos_token."""
    rendered = f"{BOS}[INST] What is 2+2? [/INST]"
    text, add_bos = resolve_native_prompt_text(rendered, BOS, model_wants_bos=True)
    tokens = _FakeTokenizer().tokenize(text.encode("utf-8"), add_bos=add_bos, special=True)
    assert tokens.count(BOS_ID) == 1
    assert tokens[0] == BOS_ID


def test_single_bos_when_template_does_not_embed_bos():
    rendered = "<|im_start|>user\nWhat is 2+2?<|im_end|>\n<|im_start|>assistant"
    text, add_bos = resolve_native_prompt_text(rendered, BOS, model_wants_bos=True)
    tokens = _FakeTokenizer().tokenize(text.encode("utf-8"), add_bos=add_bos, special=True)
    assert tokens.count(BOS_ID) == 1
    assert tokens[0] == BOS_ID


def test_stop_list_includes_both_eos_and_distinct_eot():
    # Llama 3 style: eos_token = "<|end_of_text|>", eot_token = "<|eot_id|>"
    stops = build_native_stop_list("<|end_of_text|>", "<|eot_id|>")
    assert stops == ["<|end_of_text|>", "<|eot_id|>"]


def test_stop_list_gemma_style():
    stops = build_native_stop_list("<eos>", "<end_of_turn>")
    assert stops == ["<eos>", "<end_of_turn>"]


def test_stop_list_phi3_style():
    stops = build_native_stop_list("<|endoftext|>", "<|end|>")
    assert stops == ["<|endoftext|>", "<|end|>"]


def test_stop_list_dedups_when_eot_equals_eos():
    stops = build_native_stop_list("</s>", "</s>")
    assert stops == ["</s>"]


def test_stop_list_eos_only_when_model_has_no_dedicated_eot():
    stops = build_native_stop_list("<|im_end|>", "")
    assert stops == ["<|im_end|>"]


def test_stop_list_empty_when_neither_present():
    assert build_native_stop_list("", "") == []


def test_check_context_budget_passes_when_it_fits():
    check_context_budget(prompt_token_count=100, max_tokens=256, n_ctx=2048)  # must not raise


def test_check_context_budget_raises_when_it_does_not_fit():
    with pytest.raises(RuntimeError, match="Context budget exceeded"):
        check_context_budget(prompt_token_count=2000, max_tokens=1024, n_ctx=2048)


def test_check_context_budget_exact_boundary_is_not_exceeded():
    # prompt + max_tokens == n_ctx exactly: fits, does not raise.
    check_context_budget(prompt_token_count=1792, max_tokens=256, n_ctx=2048)


def test_check_context_budget_one_token_over_raises():
    with pytest.raises(RuntimeError):
        check_context_budget(prompt_token_count=1793, max_tokens=256, n_ctx=2048)
