"""Rendering engine: turns templates + a spec into Sentences with typed spans.

A ``DocContext`` lives for one document (a narrative, or a whole dialogue) so
that first-mention / pronoun choices and coreference persist across turns.
Language-independent choices (date style, mention kind, amount style) are
drawn from an rng keyed by the spec *family*, so all language versions and
minimal-pair siblings of a case make the same surface decisions.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

from lexvaani.schemas.common import IssueId, LangVariant
from lexvaani.schemas.spec import ScenarioSpec, SpecEvent

from . import dates as D
from .lexicon import (HINDI, case_form, item, lexicon, name_in_script, noun_forms, place, pronoun,
                      render_amount)
from .markup import Sentence, render

V = LangVariant


def keyed_rng(*parts: object) -> random.Random:
    import hashlib
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


ORG_TYPES_AS_PERSONLIKE = set()


@dataclass
class DocContext:
    spec: ScenarioSpec
    variant: LangVariant
    family: str
    difficulty: str
    mentioned: dict[str, int] = field(default_factory=dict)     # node -> mention count
    item_mentioned: set[str] = field(default_factory=set)
    mention_seq: int = 0
    timex_seq: int = 0
    names: dict[str, list[str]] = field(default_factory=dict)

    # ------------------------------------------------------------ lookup
    def entity_for(self, issue: IssueId | None, slot: str):
        ref = f"{issue.value}:{slot}" if issue else None
        for p in self.spec.cast:
            if ref and ref in p.refs:
                return p
        for p in self.spec.cast:
            if p.slot == slot:
                return p
        return None

    def value_for(self, issue: IssueId | None, slot: str):
        ref = f"{issue.value}:{slot}" if issue else None
        for v in self.spec.values:
            if ref and ref in v.refs:
                return v
        for v in self.spec.values:
            if v.slot == slot:
                return v
        return None

    def gender_code(self, issue: IssueId | None, slot: str) -> str:
        if slot == "SPK":
            return {"female": "f", "male": "m"}.get(self.spec.metadata.gender.value, "m")
        if slot == "ITEM":
            v = self.value_for(issue, slot)
            return item(v.key)["g"] if v else "m"
        p = self.entity_for(issue, slot)
        if p is None or p.is_org:
            return "n"
        return {"female": "f", "male": "m"}.get(p.gender, "n")

    def next_mention_id(self) -> str:
        self.mention_seq += 1
        return f"m{self.mention_seq}"

    def next_timex_id(self) -> str:
        self.timex_seq += 1
        return f"t{self.timex_seq}"

    # ---------------------------------------------------------- mentions
    def person_mention(self, sent: Sentence, issue: IssueId | None, slot: str, case: str | None) -> None:
        p = self.entity_for(issue, slot)
        if p is None:
            raise KeyError(f"no entity for slot {slot} ({issue})")
        if p.is_org:
            raise ValueError(f"organisation slot {slot} must be written as a tagged literal")
        v = self.variant
        force_pron = bool(case and case.startswith("pron"))
        if force_pron:
            case = case[5:] or "nom"
        count = self.mentioned.get(p.node_id, 0)
        bare, named = noun_forms(p.noun, p.gender, v)
        name = name_in_script(self._name_triplet(p), v) if p.name else None
        kind = "nominal"
        form = None
        if force_pron and count > 0:
            kind = "pronoun"
        elif count == 0:
            form, kind = named, ("name" if (p.name and "{N}" in str(named)) else "nominal")
            if not p.name and isinstance(named, str) and "{N}" in named:
                form = bare
        else:
            r = keyed_rng(self.family, p.node_id, count).random()
            pron_p = {"easy": 0.0, "medium": 0.3, "hard": 0.5}[self.difficulty]
            if r < pron_p and not p.is_minor:
                kind = "pronoun"
            elif p.name and r < pron_p + (1 - pron_p) / 2:
                kind, form = "name", "{N}"
            else:
                kind, form = "nominal", bare
        if kind == "pronoun":
            g = {"female": "female", "male": "male"}.get(p.gender, "n")
            text, suffix = pronoun(v, g, case or "nom"), ""
        else:
            res = case_form(form, v, case or "nom", name)
            if res is None:   # fall back to the bare nominal for an unavailable case
                res = case_form(bare, v, case or "nom", name)
            if res is None:
                raise ValueError(f"no case form {case} for noun {p.noun} ({v.value})")
            text, suffix = res
        self.mentioned[p.node_id] = count + 1
        sent.add_span(text, "mention", node_id=p.node_id, etype="PERSON", mkind=kind,
                      mention_id=self.next_mention_id())
        sent.add(suffix)

    def _name_triplet(self, p) -> list[str]:
        if p.node_id in self.names:
            return self.names[p.node_id]
        for group in lexicon()["names"].values():
            for g in ("m", "f"):
                for trip in group[g]:
                    if trip[0] == p.name:
                        self.names[p.node_id] = trip
                        return trip
        raise KeyError(p.name)

    def literal_mention(self, sent: Sentence, issue: IssueId | None, text: str, slot: str, kind: str) -> None:
        p = self.entity_for(issue, slot)
        if p is None:
            raise KeyError(f"no entity for literal slot {slot}")
        etype = {"organization": "ORGANIZATION", "account": "ACCOUNT", "asset": "ASSET"}.get(p.role, "PERSON") \
            if p.is_org else "PERSON"
        self.mentioned[p.node_id] = self.mentioned.get(p.node_id, 0) + 1
        sent.add_span(text, "mention", node_id=p.node_id, etype=etype,
                      mkind="pronoun" if kind == "pron" else "nominal", mention_id=self.next_mention_id())

    # ------------------------------------------------------------ values
    def date_expr(self, event: SpecEvent, must_resolve: bool) -> D.DateExpr:
        ev = dt.date.fromisoformat(event.date)
        conv = dt.date.fromisoformat(self.spec.conversation_date)
        style = D.choose_style(ev, conv, self.difficulty, keyed_rng(self.family, event.element_id, "date"),
                               must_resolve_regime=must_resolve)
        return D.choose(ev, conv, self.variant, self.difficulty, keyed_rng(self.family, event.event_id, "d2"),
                        style=style, must_resolve_regime=must_resolve)

    def add_date(self, sent: Sentence, event: SpecEvent | None, must_resolve: bool) -> None:
        if event is None:
            raise ValueError("DATE slot outside an event fact")
        e = self.date_expr(event, must_resolve)
        sent.add(e.pre)
        sent.add_span(e.core, "timex", ttype=e.type, value=e.value, approximate=e.approximate,
                      anchor=self.spec.conversation_date, event_id=event.event_id,
                      timex_id=self.next_timex_id(), mention_id=self.next_mention_id())
        sent.add(e.post)

    def add_amount(self, sent: Sentence, issue: IssueId | None, slot: str, override: int | None = None) -> None:
        v = self.value_for(issue, slot)
        amount = override if override is not None else int(v.value)
        style = "words" if keyed_rng(self.family, slot, "amt").random() < 0.4 else "digits"
        sent.add_span(render_amount(amount, self.variant, style), "mention", node_id=None, etype="MONEY",
                      mkind="value", value=f"INR {amount}", mention_id=self.next_mention_id())

    def add_item(self, sent: Sentence, issue: IssueId | None, slot: str, case: str | None) -> None:
        v = self.value_for(issue, slot)
        forms = item(v.key)[self.variant.value]
        text = forms[0] if v.node_id not in self.item_mentioned else forms[1]
        self.item_mentioned.add(v.node_id)
        if case == "obl" and self.variant in HINDI:
            for a, b in (("मेरा ", "मेरे "), ("हमारा ", "हमारे "), ("mera ", "mere "), ("hamara ", "hamare "),
                         ("नया ", "नए "), ("naya ", "naye ")):
                if text.startswith(a) or f" {a}" in text:
                    text = text.replace(a, b, 1)
        sent.add_span(text, "mention", node_id=v.node_id, etype="ASSET", mkind="nominal",
                      mention_id=self.next_mention_id())

    def add_place(self, sent: Sentence, issue: IssueId | None, slot: str, case: str | None) -> None:
        v = self.value_for(issue, slot)
        entry = place(v.key)
        key = self.variant.value
        if case == "obl" and self.variant in HINDI:
            key = f"{key}_obl" if self.variant == V.HI_EN_LATN else "hi_obl"
        sent.add_span(entry[key], "mention", node_id=None, etype="LOCATION", mkind="nominal",
                      value=v.key, mention_id=self.next_mention_id())

    def add_idnum(self, sent: Sentence, issue: IssueId | None, slot: str) -> None:
        v = self.value_for(issue, slot)
        sent.add_span(v.value, "mention", node_id=None, etype="IDENTIFIER", mkind="value", value=v.value,
                      mention_id=self.next_mention_id())

    # ------------------------------------------------------------ render
    def render(self, template: str, issue: IssueId | None, event: SpecEvent | None = None,
               evidence_id: str | None = None, must_resolve: bool = False,
               amount_override: int | None = None) -> Sentence:
        def slot_renderer(sent: Sentence, slot: str, case: str | None) -> None:
            if slot == "DATE":
                self.add_date(sent, event, must_resolve)
            elif slot.startswith("AMOUNT"):
                self.add_amount(sent, issue, slot, amount_override)
            elif slot == "ITEM":
                self.add_item(sent, issue, slot, case)
            elif slot == "PLACE":
                self.add_place(sent, issue, slot, case)
            elif slot == "IDNUM":
                self.add_idnum(sent, issue, slot)
            else:
                self.person_mention(sent, issue, slot, case)

        def literal(sent: Sentence, text: str, tags: list[str]) -> None:
            start = len(sent.text)
            sent.add(text)
            end = len(sent.text)
            for t in tags:
                if t == "TRIG":
                    sent.spans.append(_rs(start, end, "trigger", event_id=event.event_id if event else None))
                elif t == "NEG":
                    sent.spans.append(_rs(start, end, "neg"))
                elif t == "EVD":
                    sent.spans.append(_rs(start, end, "mention", node_id=evidence_id, etype="EVIDENCE",
                                          mkind="nominal", mention_id=self.next_mention_id()))
                elif t.startswith("TIMEX:"):
                    ttype, value = D.special_timex(t.split(":", 1)[1],
                                                   dt.date.fromisoformat(self.spec.conversation_date))
                    sent.spans.append(_rs(start, end, "timex", ttype=ttype, value=value, approximate=False,
                                          anchor=self.spec.conversation_date, event_id=None,
                                          timex_id=self.next_timex_id(), mention_id=self.next_mention_id()))
                elif t.startswith("@"):
                    slot, _, kind = t[1:].partition(":")
                    sent.text = sent.text[:start]
                    self.literal_mention(sent, issue, text, slot, kind)
                else:
                    raise ValueError(f"unknown tag {t}")

        return render(template, slot_renderer, lambda s: self.gender_code(issue, s), literal)


def _rs(start: int, end: int, kind: str, **meta):
    from .markup import RSpan
    return RSpan(start, end, kind, meta)
