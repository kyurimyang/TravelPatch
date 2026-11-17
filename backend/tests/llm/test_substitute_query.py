from app.llm.provider import LLMOutputError
from app.llm.substitute_query import SubstituteQuery, substitute_query


class FakeProvider:
    def __init__(self, answer: SubstituteQuery | Exception) -> None:
        self.answer = answer
        self.user: str | None = None

    def complete_json(self, *, system, user, schema):
        self.user = user
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_uses_the_kind_of_place_the_model_names():
    fake = FakeProvider(SubstituteQuery(query=" 이자카야 "))
    assert substitute_query(fake, "이자카야 저녁", "meal") == "이자카야"
    assert "이자카야 저녁" in fake.user and "meal" in fake.user


def test_falls_back_to_the_title_when_the_model_fails():
    assert substitute_query(FakeProvider(LLMOutputError("x")), "라멘 점심", "meal") == "라멘 점심"


def test_falls_back_to_the_title_when_the_model_does_not_know():
    assert (
        substitute_query(FakeProvider(SubstituteQuery(query=None)), "저녁 약속", "meal")
        == "저녁 약속"
    )


def test_falls_back_to_the_title_for_a_too_long_answer():
    long = "가" * 31
    assert substitute_query(FakeProvider(SubstituteQuery(query=long)), "카페", "cafe") == "카페"
