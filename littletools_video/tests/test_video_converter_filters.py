import shutil
import subprocess
import unittest


class TestCQ40ScaleFilter(unittest.TestCase):
    def test_filter_string_has_escaped_commas(self) -> None:
        # Deferred import to avoid side-effects during test discovery
        from littletools_video.video_converter import _get_cq40_scale_filter

        flt = _get_cq40_scale_filter()
        # Should escape commas to avoid FFmpeg splitting the filter chain
        self.assertIn("if(gt(iw\\,ih)", flt)
        self.assertIn("-2\\,720", flt)
        self.assertIn("720\\,-2)", flt)
        # No inline flags in scale
        self.assertNotIn("flags=", flt)

    def test_filter_parses_in_ffmpeg(self) -> None:
        # Skip if ffmpeg is not available in PATH
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg not available")

        from littletools_video.video_converter import _get_cq40_scale_filter

        flt = _get_cq40_scale_filter()
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1920x1080:d=0.1",
            "-sws_flags",
            "lanczos",
            "-vf",
            flt,
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True)
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"ffmpeg failed to parse filter: {proc.stderr.decode(errors='ignore')}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()



