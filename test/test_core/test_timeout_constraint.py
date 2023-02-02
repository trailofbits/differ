from differ.core import TimeoutConstraint


class TestTimeoutConstraint:
    def test_load_dict(self):
        assert TimeoutConstraint.load_dict({
            'seconds': 5,
            'expected': True
        }) == TimeoutConstraint(5, True)

    def test_load_dict_int(self):
        assert TimeoutConstraint.load_dict(5) == TimeoutConstraint(5)
