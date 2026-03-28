import pytest
from src.models.database import (
    Interview,
    Speaker,
    AudioSegment,
    FaceFrame,
    EmotionNode,
    ProcessingStatus,
)


@pytest.fixture
def interview_data():
    return {
        "id": "test-interview-123",
        "filename": "test_video.mp4",
        "file_path": "/data/uploads/test_video.mp4",
        "duration": 600.0,
        "fps": 30.0,
        "resolution": "1920x1080",
        "status": ProcessingStatus.PENDING.value,
    }


def test_create_interview(db_session, interview_data):
    interview = Interview(**interview_data)
    db_session.add(interview)
    db_session.commit()

    result = db_session.query(Interview).filter(Interview.id == interview_data["id"]).first()
    assert result is not None
    assert result.filename == "test_video.mp4"
    assert result.duration == 600.0


def test_interview_relationships(db_session, interview_data):
    interview = Interview(**interview_data)
    db_session.add(interview)
    db_session.commit()

    speaker = Speaker(
        id="speaker-1",
        interview_id=interview.id,
        label="访员",
        color="#1890ff",
    )
    db_session.add(speaker)

    segment = AudioSegment(
        id="segment-1",
        interview_id=interview.id,
        speaker_id=speaker.id,
        start_time=0.0,
        end_time=5.0,
        transcript="测试转录文本",
    )
    db_session.add(segment)
    db_session.commit()

    db_session.refresh(interview)
    assert len(interview.speakers) == 1
    assert len(interview.segments) == 1


def test_face_frame_storage(db_session, interview_data):
    interview = Interview(**interview_data)
    db_session.add(interview)
    db_session.commit()

    face_frame = FaceFrame(
        id="face-1",
        interview_id=interview.id,
        timestamp=1.5,
        face_bbox=[100, 100, 200, 200],
        landmarks=[[x, y, z] for x in range(468)],
        action_units={"AU01": 0.5, "AU12": 0.8},
    )
    db_session.add(face_frame)
    db_session.commit()

    result = db_session.query(FaceFrame).filter(FaceFrame.id == "face-1").first()
    assert result is not None
    assert result.action_units["AU01"] == 0.5


def test_emotion_node_storage(db_session, interview_data):
    interview = Interview(**interview_data)
    db_session.add(interview)
    db_session.commit()

    emotion_node = EmotionNode(
        id="emotion-1",
        interview_id=interview.id,
        timestamp=10.0,
        source="audio",
        label="紧张",
        intensity=0.8,
        confidence=0.9,
        audio_emotion={"anxious": 0.8, "neutral": 0.2},
    )
    db_session.add(emotion_node)
    db_session.commit()

    result = db_session.query(EmotionNode).filter(EmotionNode.id == "emotion-1").first()
    assert result is not None
    assert result.label == "紧张"
    assert result.source == "audio"
