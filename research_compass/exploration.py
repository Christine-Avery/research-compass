"""Small, inspectable steps between a vague interest and search queries."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchBranch:
    key: str
    title: str
    purpose: str
    query: str
    focus_method: str = ""
    required_methods: tuple[str, ...] = ()
    query_aliases: tuple[str, ...] = ()


LENSES = (
    ("overview", "整体了解", "先看这个领域正在研究什么", ""),
    ("methods", "常见方法", "寻找常用方法和技术路线", "methods approaches"),
    ("applications", "应用场景", "寻找具体任务和使用场景", "applications"),
    ("challenges", "困难与局限", "寻找论文讨论的挑战，不据此断言研究空白", "challenges limitations"),
)


def clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def build_branches(interest: str, context: str = "") -> list[SearchBranch]:
    """Build editable query suggestions without claiming they are AI generated."""
    interest = clean_text(interest)
    context = clean_text(context)
    if not interest:
        raise ValueError("研究兴趣不能为空")

    base = " ".join(part for part in (interest, context) if part)
    return [
        SearchBranch(key, title, purpose, clean_text(f"{base} {suffix}"))
        for key, title, purpose, suffix in LENSES
    ]


def default_branch_keys(focus: str) -> list[str]:
    if focus in {"methods", "applications", "challenges"}:
        return ["overview", focus]
    return ["overview", "methods", "applications"]
