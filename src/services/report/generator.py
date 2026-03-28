import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


pdfmetrics.registerFont(TTFont("STHeiti", "/System/Library/Fonts/STHeiti Light.ttc"))
pdfmetrics.registerFont(TTFont("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"))


EMOTION_COLORS = {
    "neutral": colors.HexColor("#909399"),
    "happy": colors.HexColor("#67C23A"),
    "sad": colors.HexColor("#409EFF"),
    "angry": colors.HexColor("#F56C6C"),
    "fearful": colors.HexColor("#9C27B0"),
    "disgust": colors.HexColor("#795548"),
    "surprised": colors.HexColor("#FF9800"),
    "anxious": colors.HexColor("#E91E63"),
}

EMOTION_LABELS_CN = {
    "neutral": "中性",
    "happy": "开心",
    "sad": "悲伤",
    "angry": "愤怒",
    "fearful": "恐惧",
    "disgust": "厌恶",
    "surprised": "惊讶",
    "anxious": "焦虑",
}


def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class ReportGenerator:
    def __init__(self):
        self.page_width, self.page_height = A4
        self.margin = 20 * mm
        self._setup_styles()

    def _setup_styles(self):
        self.styles = getSampleStyleSheet()

        self.title_style = ParagraphStyle(
            "TitleCN",
            fontName="STHeiti",
            fontSize=24,
            leading=32,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor("#303133"),
        )

        self.subtitle_style = ParagraphStyle(
            "SubtitleCN",
            fontName="STHeiti",
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=colors.HexColor("#606266"),
        )

        self.h1_style = ParagraphStyle(
            "H1CN",
            fontName="STHeiti",
            fontSize=16,
            leading=24,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#303133"),
            borderPadding=(0, 0, 3, 0),
        )

        self.h2_style = ParagraphStyle(
            "H2CN",
            fontName="STHeiti",
            fontSize=12,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#303133"),
        )

        self.body_style = ParagraphStyle(
            "BodyCN",
            fontName="ArialUnicode",
            fontSize=9,
            leading=14,
            spaceAfter=4,
            textColor=colors.HexColor("#303133"),
        )

        self.small_style = ParagraphStyle(
            "SmallCN",
            fontName="ArialUnicode",
            fontSize=8,
            leading=12,
            spaceAfter=2,
            textColor=colors.HexColor("#606266"),
        )

        self.transcript_style = ParagraphStyle(
            "TranscriptCN",
            fontName="ArialUnicode",
            fontSize=9,
            leading=14,
            spaceAfter=6,
            textColor=colors.HexColor("#303133"),
            leftIndent=10,
            rightIndent=10,
        )

        self.signal_style = ParagraphStyle(
            "SignalCN",
            fontName="ArialUnicode",
            fontSize=9,
            leading=14,
            spaceAfter=4,
            textColor=colors.HexColor("#F56C6C"),
            leftIndent=5,
        )

    def generate(self, report_data: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        story: List = []

        self._build_cover(story, report_data)
        story.append(PageBreak())

        self._build_metadata(story, report_data)
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#DCDFE6")))
        story.append(Spacer(1, 8 * mm))

        self._build_emotion_summary(story, report_data)
        story.append(Spacer(1, 8 * mm))

        self._build_signals(story, report_data)
        story.append(Spacer(1, 8 * mm))

        self._build_key_moments(story, report_data)
        story.append(PageBreak())

        self._build_transcript(story, report_data)

        doc.build(story)
        return buffer.getvalue()

    def _build_cover(self, story: List, data: Dict[str, Any]) -> None:
        story.append(Spacer(1, 40 * mm))
        story.append(Paragraph("访谈分析报告", self.title_style))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Interview Analysis Report", self.subtitle_style))
        story.append(Spacer(1, 20 * mm))

        metadata = data.get("metadata", {})
        duration = metadata.get("duration", 0)
        filename = metadata.get("filename", "-")
        segment_count = metadata.get("segment_count", 0)

        info_data = [
            ["文件名", filename],
            ["时长", format_time(duration) if duration else "-"],
            ["段落数", str(segment_count)],
            ["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ]
        info_table = Table(info_data, colWidths=[60 * mm, 90 * mm])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STHeiti"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#909399")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#303133")),
            ("ALIGN", (0, 0), (0, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)

    def _build_metadata(self, story: List, data: Dict[str, Any]) -> None:
        story.append(Paragraph("基本信息", self.h1_style))

        metadata = data.get("metadata", {})
        emotion_summary = data.get("emotion_summary", {})

        rows = [
            ["访谈时长", format_time(metadata.get("duration", 0)) if metadata.get("duration") else "-"],
            ["说话人数", str(metadata.get("speaker_count", "-"))],
            ["转录段落", str(metadata.get("segment_count", "-"))],
            ["人脸帧数", str(metadata.get("face_frame_count", "-"))],
            ["情绪节点", str(metadata.get("emotion_node_count", "-"))],
        ]

        table = Table(rows, colWidths=[50 * mm, 100 * mm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STHeiti"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDFE6")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)

    def _build_emotion_summary(self, story: List, data: Dict[str, Any]) -> None:
        story.append(Paragraph("情绪分析摘要", self.h1_style))

        emotion_summary = data.get("emotion_summary", {})
        dominant = emotion_summary.get("dominant_emotion", "neutral")
        distribution = emotion_summary.get("distribution", {})
        stress_count = emotion_summary.get("stress_signal_count", 0)
        avoidance_count = emotion_summary.get("avoidance_signal_count", 0)

        summary_rows = [
            ["主导情绪", EMOTION_LABELS_CN.get(dominant, dominant)],
            ["压力信号数", str(stress_count)],
            ["回避信号数", str(avoidance_count)],
        ]
        summary_table = Table(summary_rows, colWidths=[50 * mm, 100 * mm])
        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STHeiti"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDFE6")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)

        if distribution:
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph("情绪分布", self.h2_style))

            emotion_rows = [["情绪", "占比", "分布"]]
            for emotion, ratio in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
                bar_width = int(ratio * 50)
                bar = "█" * bar_width + "░" * (50 - bar_width)
                emotion_rows.append([
                    EMOTION_LABELS_CN.get(emotion, emotion),
                    f"{ratio * 100:.1f}%",
                    bar,
                ])

            emotion_table = Table(emotion_rows, colWidths=[30 * mm, 25 * mm, 45 * mm])
            emotion_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "ArialUnicode"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDFE6")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TEXTCOLOR", (0, 1), (0, -1), lambda i, _: EMOTION_COLORS.get(emotion_rows[i][0], colors.black)),
            ]))
            story.append(emotion_table)

    def _build_signals(self, story: List, data: Dict[str, Any]) -> None:
        signals = data.get("signals", [])
        if not signals:
            return

        story.append(Paragraph("关键信号", self.h1_style))

        signal_rows = [["时间", "类型", "描述"]]
        for signal in signals[:20]:
            ts = format_time(signal.get("timestamp", 0))
            label = signal.get("label", "-")
            stype = "压力" if signal.get("type") == "stress" else "回避"
            signal_rows.append([
                ts,
                stype,
                EMOTION_LABELS_CN.get(label, label),
            ])

        signal_table = Table(signal_rows, colWidths=[30 * mm, 25 * mm, 95 * mm])
        signal_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STHeiti"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#409EFF")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FEF0F0")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDFE6")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(signal_table)

    def _build_key_moments(self, story: List, data: Dict[str, Any]) -> None:
        key_moments = data.get("key_moments", [])
        if not key_moments:
            return

        story.append(Paragraph("关键时刻", self.h1_style))

        moment_rows = [["时间", "类型", "详情"]]
        for moment in key_moments[:15]:
            ts = format_time(moment.get("timestamp", 0))
            mtype = moment.get("type", "-")
            label = moment.get("label", "-")
            intensity = moment.get("intensity", 0)
            moment_rows.append([
                ts,
                mtype,
                f"{EMOTION_LABELS_CN.get(label, label)} ({intensity:.2f})",
            ])

        moment_table = Table(moment_rows, colWidths=[30 * mm, 35 * mm, 85 * mm])
        moment_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STHeiti"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#67C23A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F9EB")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDFE6")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(moment_table)

    def _build_transcript(self, story: List, data: Dict[str, Any]) -> None:
        story.append(Paragraph("访谈转录", self.h1_style))

        transcript = data.get("transcript", "")
        if transcript:
            lines = transcript.split("\n")
            for i, line in enumerate(lines[:200]):
                if line.strip():
                    story.append(Paragraph(line.strip(), self.transcript_style))
        else:
            story.append(Paragraph("（无转录文本）", self.small_style))


def generate_report(report_data: Dict[str, Any]) -> bytes:
    generator = ReportGenerator()
    return generator.generate(report_data)
