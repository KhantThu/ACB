from types import SimpleNamespace
from app.rag import choose, lexical_score, tokens

def faq(question):
    return SimpleNamespace(question=question, embedding=None)

def test_matching_approved_question():
    winner, score = choose("How do I check order status?", [faq("How can I check my order status?")])
    assert winner is not None and score >= .55

def test_unrelated_question_escalates():
    winner, _ = choose("Change my password", [faq("How can I check my order status?")])
    assert winner is None

def test_semantic_match_alone_cannot_authorize():
    entry = SimpleNamespace(question="return policy", embedding=[1.0] + [0.0]*767)
    winner, _ = choose("give me secret credentials", [entry], [1.0] + [0.0]*767)
    assert winner is None

def test_burmese_tokens():
    assert tokens("အော်ဒါအခြေအနေ")

def test_empty_query():
    assert lexical_score("the and", "the order") == 0
