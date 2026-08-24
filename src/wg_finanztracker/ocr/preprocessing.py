from pathlib import Path

import cv2
import numpy as np


def preprocess_image(
    image_path: str | Path,
) -> np.ndarray:
    """
    Gibt die Standard-Preprocessing-Variante zurück.

    Wird aus Kompatibilitätsgründen behalten.
    """
    return preprocess_variants(image_path)["clahe"]


def preprocess_variants(
    image_path: str | Path,
) -> dict[str, np.ndarray]:
    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError("Bild konnte nicht geladen werden.")

    image = _extract_receipt(image)

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    gray = _resize_for_ocr(gray)

    gray = cv2.fastNlMeansDenoising(
        gray,
        None,
        7,
        7,
        21,
    )

    # Lokale Schatten und der bei vielen Bons
    # sichtbare Rückseitendruck werden durch eine
    # Schätzung des Papierhintergrunds abgeschwächt.
    background = cv2.GaussianBlur(
        gray,
        (0, 0),
        sigmaX=35,
        sigmaY=35,
    )

    normalized = cv2.divide(
        gray,
        background,
        scale=255,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    raw_clahe_image = _deskew(clahe.apply(gray))

    normalized_clahe_image = clahe.apply(normalized)

    # Deskew auf derselben Grundlage wie
    # unsere zuvor funktionierende Pipeline.
    normalized_clahe_image = _deskew(normalized_clahe_image)

    _, otsu_image = cv2.threshold(
        normalized_clahe_image,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    adaptive_image = cv2.adaptiveThreshold(
        normalized_clahe_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    return {
        "clahe": raw_clahe_image,
        "normalized": normalized_clahe_image,
        "otsu": otsu_image,
        "adaptive": adaptive_image,
    }


def _resize_for_ocr(
    image: np.ndarray,
) -> np.ndarray:
    height, width = image.shape[:2]

    largest_dimension = max(
        height,
        width,
    )

    # Tesseract profitiert von ausreichend großen
    # Zeichen, wird bei Handyfotos mit 8.000+ Pixeln
    # aber nur langsamer und speicherhungriger.
    target_dimension = 3600

    scale = target_dimension / largest_dimension

    if 0.90 <= scale <= 1.20:
        return image

    scale = min(scale, 2.0)

    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA

    return cv2.resize(
        image,
        None,
        fx=scale,
        fy=scale,
        interpolation=interpolation,
    )


def _extract_receipt(
    image: np.ndarray,
) -> np.ndarray:
    original_height, original_width = image.shape[:2]

    max_detection_size = 1600

    largest_dimension = max(
        original_height,
        original_width,
    )

    if largest_dimension > max_detection_size:
        scale = max_detection_size / largest_dimension

        detection_image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )
    else:
        scale = 1.0
        detection_image = image.copy()

    gray = cv2.cvtColor(
        detection_image,
        cv2.COLOR_BGR2GRAY,
    )

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    edges = cv2.Canny(
        blurred,
        50,
        150,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (5, 5),
    )

    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    image_area = detection_image.shape[0] * detection_image.shape[1]

    contours = sorted(
        contours,
        key=cv2.contourArea,
        reverse=True,
    )

    receipt_points = _find_four_corner_receipt(
        contours,
        image_area,
    )

    if receipt_points is None:
        receipt_points = _find_receipt_rectangle(
            edges,
            image_area,
        )

    if receipt_points is None:
        return image

    receipt_points /= scale

    receipt_points = _expand_points(
        receipt_points,
        image.shape,
    )

    ordered_points = _order_points(receipt_points)

    return _warp_perspective(
        image,
        ordered_points,
    )


def _find_four_corner_receipt(
    contours: list[np.ndarray],
    image_area: float,
) -> np.ndarray | None:
    for contour in contours[:30]:
        area = cv2.contourArea(contour)

        # Kleine geschlossene Rahmen innerhalb des
        # Bons (Coupons, PAYBACK-Boxen, QR-Codes)
        # dürfen nicht als kompletter Bon gelten.
        if area < image_area * 0.18:
            continue

        perimeter = cv2.arcLength(
            contour,
            True,
        )

        approximate = cv2.approxPolyDP(
            contour,
            0.02 * perimeter,
            True,
        )

        if len(approximate) != 4:
            continue

        if not cv2.isContourConvex(approximate):
            continue

        return approximate.reshape(4, 2).astype(np.float32)

    return None


def _find_receipt_rectangle(
    edges: np.ndarray,
    image_area: float,
) -> np.ndarray | None:
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (25, 25),
    )

    connected = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )

    contours, _ = cv2.findContours(
        connected,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    candidates: list[tuple[float, np.ndarray]] = []

    for contour in contours:
        contour_area = cv2.contourArea(contour)

        if contour_area < image_area * 0.18:
            continue

        rectangle = cv2.minAreaRect(contour)

        width, height = rectangle[1]

        if width <= 0 or height <= 0:
            continue

        rectangle_area = width * height

        if rectangle_area > image_area * 0.85:
            continue

        short_side = min(
            width,
            height,
        )

        long_side = max(
            width,
            height,
        )

        if short_side == 0:
            continue

        aspect_ratio = long_side / short_side

        if not (1.2 <= aspect_ratio <= 6.0):
            continue

        fill_ratio = contour_area / rectangle_area

        score = contour_area * fill_ratio

        points = cv2.boxPoints(rectangle).astype(np.float32)

        candidates.append(
            (
                score,
                points,
            )
        )

    if not candidates:
        return None

    _, best_points = max(
        candidates,
        key=lambda candidate: candidate[0],
    )

    return best_points


def _expand_points(
    points: np.ndarray,
    image_shape: tuple[int, ...],
) -> np.ndarray:
    """Gibt dem erkannten Bon einen kleinen sicheren Rand."""

    center = points.mean(axis=0)

    expanded = center + (points - center) * 1.025

    height, width = image_shape[:2]

    expanded[:, 0] = np.clip(
        expanded[:, 0],
        0,
        width - 1,
    )

    expanded[:, 1] = np.clip(
        expanded[:, 1],
        0,
        height - 1,
    )

    return expanded.astype(np.float32)


def _order_points(
    points: np.ndarray,
) -> np.ndarray:
    ordered = np.zeros(
        (4, 2),
        dtype=np.float32,
    )

    coordinate_sum = points.sum(axis=1)

    coordinate_difference = np.diff(
        points,
        axis=1,
    ).flatten()

    ordered[0] = points[np.argmin(coordinate_sum)]

    ordered[1] = points[np.argmin(coordinate_difference)]

    ordered[2] = points[np.argmax(coordinate_sum)]

    ordered[3] = points[np.argmax(coordinate_difference)]

    return ordered


def _warp_perspective(
    image: np.ndarray,
    points: np.ndarray,
) -> np.ndarray:
    top_left = points[0]
    top_right = points[1]
    bottom_right = points[2]
    bottom_left = points[3]

    top_width = np.linalg.norm(top_right - top_left)

    bottom_width = np.linalg.norm(bottom_right - bottom_left)

    left_height = np.linalg.norm(bottom_left - top_left)

    right_height = np.linalg.norm(bottom_right - top_right)

    target_width = int(
        max(
            top_width,
            bottom_width,
        )
    )

    target_height = int(
        max(
            left_height,
            right_height,
        )
    )

    if target_width < 50 or target_height < 50:
        return image

    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [
                target_width - 1,
                target_height - 1,
            ],
            [
                0,
                target_height - 1,
            ],
        ],
        dtype=np.float32,
    )

    matrix = cv2.getPerspectiveTransform(
        points,
        destination,
    )

    return cv2.warpPerspective(
        image,
        matrix,
        (
            target_width,
            target_height,
        ),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _deskew(
    image: np.ndarray,
) -> np.ndarray:
    hough_angle = _find_horizontal_line_angle(image)

    if hough_angle is not None:
        return _rotate_image(
            image,
            hough_angle,
        )

    binary = cv2.threshold(
        image,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )[1]

    coordinates = np.column_stack(np.where(binary > 0))

    if len(coordinates) == 0:
        return image

    coordinates = coordinates[:, ::-1].astype(np.float32)

    angle = cv2.minAreaRect(coordinates)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) > 15:
        return image

    return _rotate_image(
        image,
        angle,
    )


def _find_horizontal_line_angle(
    image: np.ndarray,
) -> float | None:
    """Nutzt lange Bon- und Tabellenlinien als stabile Horizontale."""

    width = image.shape[1]

    edges = cv2.Canny(
        image,
        50,
        150,
    )

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(50, width // 20),
        minLineLength=max(80, int(width * 0.18)),
        maxLineGap=max(15, int(width * 0.04)),
    )

    if lines is None:
        return None

    angles: list[float] = []

    for raw_line in lines:
        x1, y1, x2, y2 = np.asarray(raw_line).reshape(4)

        angle = float(
            np.degrees(
                np.arctan2(
                    y2 - y1,
                    x2 - x1,
                )
            )
        )

        if abs(angle) <= 15:
            angles.append(angle)

    if len(angles) < 2:
        return None

    result = float(np.median(angles))

    if abs(result) < 0.20:
        return 0.0

    return result


def _rotate_image(
    image: np.ndarray,
    angle: float,
) -> np.ndarray:
    height, width = image.shape[:2]

    center = (
        width / 2,
        height / 2,
    )

    matrix = cv2.getRotationMatrix2D(
        center,
        angle,
        1.0,
    )

    return cv2.warpAffine(
        image,
        matrix,
        (
            width,
            height,
        ),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
