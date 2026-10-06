from telemetry_identity import user_pseudonym, vendor_pseudonym


def test_user_identity_is_rotating_pseudonym_not_internal_id():
    assert len(user_pseudonym(1)) == 64
    assert user_pseudonym(1) == user_pseudonym(1)
    assert user_pseudonym(1) != user_pseudonym(2)


def test_vendor_normalization_and_separate_identity_keys():
    assert vendor_pseudonym("  Vendor   Supply ") == vendor_pseudonym("vendor supply")
    assert vendor_pseudonym("Véndor") == vendor_pseudonym("Ve\u0301ndor")
    assert vendor_pseudonym("1") != user_pseudonym(1)