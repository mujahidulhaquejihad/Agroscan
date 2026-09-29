"""One check for split-leak identity keys and keep-test-first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fix_split_leakage import keep_best_split, orig_name, pv_source


def main() -> None:
    assert orig_name("00000001_foo.jpg") == "foo.jpg"
    assert orig_name("foo.jpg") == "foo.jpg"
    assert pv_source("00000001_uuid___frec_scab 3015.JPG") == "frec_scab 3015"
    assert pv_source("train_083479.jpg") is None

    delete: set[Path] = set()
    train, valid, test = Path("train/a.jpg"), Path("valid/a.jpg"), Path("test/a.jpg")
    keep_best_split([("train", train), ("valid", valid), ("test", test)], delete)
    assert delete == {train, valid}

    delete.clear()
    keep_best_split([("train", train), ("valid", valid)], delete)
    assert delete == {train}

    delete.clear()
    keep_best_split([("train", train)], delete)
    assert delete == set()
    print("ok")


if __name__ == "__main__":
    main()
