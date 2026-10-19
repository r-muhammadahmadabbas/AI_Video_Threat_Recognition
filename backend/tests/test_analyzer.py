import numpy as np

from workers.cv_worker.analyzer import AnalyzerConfig, FrameAnalyzer
from workers.cv_worker.detector import Detection
from workers.cv_worker.weapon_detector import WeaponDetection


def make_frame() -> np.ndarray:
    return np.zeros((4, 4, 3), dtype=np.uint8)


def person(confidence: float = 0.9) -> Detection:
    return Detection(
        bbox=(0.0, 0.0, 10.0, 10.0),
        confidence=confidence,
        class_id=0,
        class_name="person",
    )


def weapon(class_name: str, confidence: float = 0.5) -> WeaponDetection:
    return WeaponDetection(
        class_name=class_name, confidence=confidence, bbox=(0.0, 0.0, 10.0, 10.0)
    )


class FakePersonModel:
    def __init__(self, detections=None):
        self.calls = 0
        self._detections = detections if detections is not None else [person()]

    def detect(self, _frame):
        self.calls += 1
        return list(self._detections)


class FakeWeaponModel:
    def __init__(self, detections=None):
        self.calls = 0
        self.resets = 0
        self._detections = detections if detections is not None else []

    def detect(self, _frame):
        self.calls += 1
        return list(self._detections)

    def reset(self):
        self.resets += 1


class FakePoseRunner:
    def __init__(self):
        self.calls = 0

    def __call__(self, _frame):
        self.calls += 1
        return np.zeros((1, 17, 2), dtype=float)


class FakeViolenceRunner:
    def __init__(self, result=True):
        self.calls = 0
        self._result = result

    def __call__(self, _frame):
        self.calls += 1
        return self._result


class TestPersonOnlyPath:
    def test_person_detections_pass_through(self):
        persons = [person(0.8), person(0.6)]
        analyzer = FrameAnalyzer(person_model=FakePersonModel(persons))

        analysis = analyzer.analyze(make_frame())

        assert analysis.persons == persons
        assert analysis.weapons == []
        assert analysis.violence is False
        assert analysis.pose_keypoints is None

    def test_optional_models_not_constructed_when_disabled(self):
        analyzer = FrameAnalyzer(
            AnalyzerConfig(weapon_enabled=False, pose_enabled=False, violence_enabled=False),
            person_model=FakePersonModel(),
        )

        analysis = analyzer.analyze(make_frame())

        assert analysis.persons
        assert analysis.weapons == []


class TestWeaponCadence:
    def test_weapon_runs_on_configured_interval(self):
        fake = FakeWeaponModel()
        analyzer = FrameAnalyzer(
            AnalyzerConfig(weapon_interval=2),
            person_model=FakePersonModel(),
            weapon_model=fake,
        )

        analyzer.analyze(make_frame())
        analyzer.analyze(make_frame())
        analyzer.analyze(make_frame())

        assert fake.calls == 2

    def test_only_threat_detections_are_returned(self):
        fake = FakeWeaponModel([weapon("person", 0.9), weapon("firearm", 0.7)])
        analyzer = FrameAnalyzer(person_model=FakePersonModel(), weapon_model=fake)

        analysis = analyzer.analyze(make_frame())

        assert [d.class_name for d in analysis.weapons] == ["firearm"]


class TestPoseAndViolenceCadence:
    def test_pose_runs_every_configured_frame(self):
        pose = FakePoseRunner()
        analyzer = FrameAnalyzer(
            AnalyzerConfig(pose_interval=2),
            person_model=FakePersonModel(),
            pose_runner=pose,
        )

        analyzer.analyze(make_frame())
        analyzer.analyze(make_frame())
        analyzer.analyze(make_frame())

        assert pose.calls == 2

    def test_pose_keypoints_are_exposed(self):
        analyzer = FrameAnalyzer(
            AnalyzerConfig(pose_interval=1),
            person_model=FakePersonModel(),
            pose_runner=FakePoseRunner(),
        )

        analysis = analyzer.analyze(make_frame())

        assert analysis.pose_keypoints is not None
        assert analysis.pose_keypoints.shape == (1, 17, 2)

    def test_violence_flag_propagates(self):
        violence = FakeViolenceRunner(result=True)
        analyzer = FrameAnalyzer(
            AnalyzerConfig(violence_interval=1),
            person_model=FakePersonModel(),
            violence_runner=violence,
        )

        assert analyzer.analyze(make_frame()).violence is True


class TestReset:
    def test_reset_restarts_cadence_and_clears_weapon_history(self):
        fake_weapon = FakeWeaponModel()
        pose = FakePoseRunner()
        analyzer = FrameAnalyzer(
            AnalyzerConfig(weapon_interval=2, pose_interval=2),
            person_model=FakePersonModel(),
            weapon_model=fake_weapon,
            pose_runner=pose,
        )

        analyzer.analyze(make_frame())
        analyzer.analyze(make_frame())
        assert fake_weapon.calls == 1

        analyzer.reset()
        analyzer.analyze(make_frame())

        assert fake_weapon.resets == 1
        assert fake_weapon.calls == 2
        assert pose.calls == 2
