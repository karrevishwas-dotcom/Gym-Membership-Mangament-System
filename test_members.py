def test_member_name():

    member_name = "Rahul Kumar"

    assert member_name != ""
    assert len(member_name) > 2


def test_member_phone():

    phone = "9876543210"

    assert phone.isdigit()
    assert len(phone) == 10


def test_member_age():

    age = 25

    assert age > 0
    assert age < 100