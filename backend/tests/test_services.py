from app.services import category_for

def test_category_classification():
    assert category_for("Code.exe", "main.py") == "coding"
    assert category_for("chrome.exe", "An article") == "browsing"
    assert category_for("Zoom.exe", "Weekly sync") == "meeting"
    assert category_for("chrome.exe", "YouTube - video") == "media"
