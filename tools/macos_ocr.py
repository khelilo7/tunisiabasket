"""The text reader built into macOS (Vision), for the Live reader: reads the bold digits of the second scoreboard layout, which tesseract gets wrong (44 as 464, 38 as nothing).

    read_digits(rgb_crop) -> "44" or ""        needs `pip install pyobjc-framework-Vision pyobjc-framework-Quartz` (tools/install_live_reader.sh does); without it
                                                `available()` is False and the reader keeps using tesseract.
"""
import re

import numpy as np

_v = None


def _load():
    global _v
    if _v is None:
        try:
            import Quartz
            import Vision
            from Foundation import NSData
            _v = (Vision, Quartz, NSData)
        except ImportError:
            _v = False
    return _v


def available():
    return bool(_load())


def _cgimage(rgb):
    _, Quartz, NSData = _load()
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w, _c = rgb.shape
    rgba = np.dstack([rgb, np.full((h, w), 255, np.uint8)])
    provider = Quartz.CGDataProviderCreateWithCFData(NSData.dataWithBytes_length_(rgba.tobytes(), rgba.nbytes))
    return Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(), Quartz.kCGImageAlphaNoneSkipLast, provider, None, False,
                                Quartz.kCGRenderingIntentDefault)


def read_digits(rgb, scale=4):
    """The number written in this picture (a few digits, light on a darker panel), or "". Marks around it (a dash, a dot) are ignored."""
    if not _load():
        return ""
    from PIL import Image
    Vision = _load()[0]
    im = Image.fromarray(np.ascontiguousarray(rgb))
    big = np.asarray(im.resize((max(1, im.width * scale), max(1, im.height * scale)), Image.LANCZOS))
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)                                               # accurate
    req.setUsesLanguageCorrection_(False)
    req.setRecognitionLanguages_(["en-US"])
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(_cgimage(big), None).performRequests_error_([req], None)
    found = [m for o in (req.results() or []) for m in re.findall(r"\d{1,3}", str(o.topCandidates_(1)[0].string()))]
    return max(found, key=len) if found else ""
