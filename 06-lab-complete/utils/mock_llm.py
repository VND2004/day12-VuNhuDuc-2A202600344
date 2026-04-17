"""Mock LLM responses for local labs without paid API access."""


def ask(question: str) -> str:
    q = question.lower()
    if "docker" in q:
        return "Docker dong goi app va dependencies de deploy nhat quan tren moi moi truong."
    if "redis" in q:
        return "Redis duoc dung de luu state dung chung giua nhieu instances theo mo hinh stateless."
    if "kubernetes" in q:
        return "Kubernetes dieu phoi container, scale service va tu dong hoi phuc khi co su co."
    return "Agent dang hoat dong tot (mock response). Ban co the hoi tiep."