"""AASHTO 2018 criteria using a locally supplied, validated table workbook.

No copyrighted radius/runoff table is distributed in this module. Equations
3-23/3-24 and §3.3.8.2.1 are implemented separately from table transcription.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile

PROFILE_ID = "aashto-green-book-2018-2019-10"
MAX_RATES = (4, 6, 8, 10, 12)
WORKBOOK_TABLE_DIGEST = (
    "bb84bc9fc5bc430fd187b3c378cc7f085779fae7dc503874329f6a127ffc6648"
)
RUNOFF_DIGEST = "a79a4a42e40cd9fac6c343e0910811509496261cde60a3686cb64003c2a27576"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def import_workbook(content_base64: str) -> dict:
    """Read only the verified radius/runoff cells; ignore macros and formulas.

    A digest pins this criteria version to the reviewed corrected transcription.
    Changing the tables requires renewed review and a new profile version.
    """
    try:
        raw = base64.b64decode(content_base64, validate=True)
        if len(raw) > 5_000_000:
            raise ValueError("Criteria workbook exceeds 5 MB.")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 20_000_000:
                raise ValueError("Expanded criteria workbook exceeds 20 MB.")
            strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                strings = [
                    "".join(t.itertext())
                    for t in ET.fromstring(
                        archive.read("xl/sharedStrings.xml")
                    ).findall("x:si", NS)
                ]
            relations = {
                n.get("Id"): n.get("Target")
                for n in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            }
            sheets = {}
            for sheet in ET.fromstring(archive.read("xl/workbook.xml")).findall(
                "x:sheets/x:sheet", NS
            ):
                target = relations[
                    sheet.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )
                ]
                path = target.lstrip("/") if target.startswith("/") else "xl/" + target
                cells = {}
                for cell in ET.fromstring(archive.read(path)).findall(
                    "x:sheetData/x:row/x:c", NS
                ):
                    if cell.find("x:f", NS) is not None:
                        raise ValueError(
                            "Criteria tables must contain published values, not workbook formulas."
                        )
                    value = cell.findtext("x:v", namespaces=NS)
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("x:is", NS).itertext())
                    elif value is not None and cell.get("t") not in {"str", "b", "e"}:
                        value = float(value)
                        if not math.isfinite(value):
                            raise ValueError("Nonfinite criteria value.")
                        if value.is_integer():
                            value = int(value)
                    cells[cell.get("r")] = value
                sheets[sheet.get("name")] = cells
        tables = {}

        def column(n):
            result = ""
            while n:
                n, r = divmod(n - 1, 26)
                result = chr(65 + r) + result
            return result

        for maximum, number in zip(MAX_RATES, range(8, 13)):
            cells = sheets[f"Table 3-{number}"]
            count = 12 if maximum == 4 else 16
            tables[str(maximum)] = {
                "speeds": [cells[f"{column(c)}6"] for c in range(3, count + 1)],
                "rows": [
                    [cells.get(f"{column(c)}{r}") for c in range(2, count + 1)]
                    for r in range(8, 60)
                    if isinstance(cells.get(f"B{r}"), (int, float))
                    or cells.get(f"B{r}") in ("NC", "RC")
                ],
            }
        digest = hashlib.sha256(
            json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != WORKBOOK_TABLE_DIGEST:
            raise ValueError(
                "Radius tables differ from the reviewed corrected AASHTO workbook; criteria review is required."
            )
        runoff_cells = sheets["Table 3-16A"]
        runoff = [
            [runoff_cells.get(f"{column(c)}{r}") for c in range(2, 33)]
            for r in range(10, 62)
        ]
        if (
            hashlib.sha256(
                json.dumps(runoff, separators=(",", ":")).encode()
            ).hexdigest()
            != RUNOFF_DIGEST
        ):
            raise ValueError(
                "Runoff cells differ from the reviewed October 2019 corrected table."
            )
        if any(not isinstance(v, (int, float)) for row in runoff for v in row):
            raise ValueError(
                "Corrected Table 3-16a must include 15–85 mph and both lane columns."
            )
        # Check transcribed runoff against the source equation as a scale check;
        # published rounding is retained, not reconstructed from this check.
        for row in runoff:
            for j, value in enumerate(row[1:]):
                expected = (
                    12
                    * row[0]
                    / 100
                    / relative_gradient(15 + 5 * (j // 2))
                    * (1.5 if j % 2 else 1)
                )
                if abs(value - expected) >= 1:
                    raise ValueError(
                        "Runoff table does not match the October 2019 correction."
                    )
        return {
            "tables": tables,
            "runoff": runoff,
            "table_digest": digest,
            "file_sha256": hashlib.sha256(raw).hexdigest(),
            "source_version": "2018 / October 2019 errata",
            "distribution_status": "User supplied locally; redistribution permission not established",
        }
    except (KeyError, TypeError, zipfile.BadZipFile, ET.ParseError, IndexError) as exc:
        raise ValueError("Not a supported, complete AASHTO criteria workbook.") from exc


def relative_gradient(speed: float) -> float:
    """§3.3.8.2.1 inverse relative slopes; interpolation in 1:gradient."""
    if speed not in range(15, 86, 5):
        raise ValueError(
            "AASHTO supports published speeds 15–85 mph in 5-mph increments."
        )
    return 1 / min(200, max(125, 200 - 2.5 * (50 - speed)))


def lane_factor(rotated_lanes: float) -> float:
    """Table 3-15 footnote, without rounding the published two-decimal factors."""
    if not 1 <= rotated_lanes <= 3.5:
        raise ValueError(
            "Rotated lane count is outside verified Table 3-15 scope (1–3.5)."
        )
    return (1 + 0.5 * (rotated_lanes - 1)) / rotated_lanes


def rate(
    pack: dict, maximum: int, speed: float, radius: float, normal: float
) -> tuple[float, str, dict]:
    """Use §3.3.5's next-smaller tabulated radius without interpolating e."""
    if maximum not in MAX_RATES:
        raise ValueError("Maximum superelevation must be 4, 6, 8, 10, or 12 percent.")
    if not pack or pack.get("table_digest") != WORKBOOK_TABLE_DIGEST:
        raise ValueError(
            "Import the reviewed AASHTO criteria workbook before automatic rate calculation."
        )
    digest = hashlib.sha256(
        json.dumps(pack.get("tables"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != WORKBOOK_TABLE_DIGEST:
        raise ValueError(
            "Saved criteria tables were changed; reimport the reviewed workbook."
        )
    if (
        hashlib.sha256(
            json.dumps(pack.get("runoff"), separators=(",", ":")).encode()
        ).hexdigest()
        != RUNOFF_DIGEST
    ):
        raise ValueError(
            "Saved runoff tables were changed; reimport the reviewed workbook."
        )
    table = pack["tables"][str(maximum)]
    speeds = [int(re.search(r"\d+", str(s)).group()) for s in table["speeds"]]
    if speed not in speeds:
        raise ValueError(
            f"Table 3-{8 + MAX_RATES.index(maximum)} does not publish speed {speed:g} mph."
        )
    col = speeds.index(speed) + 1
    rows = table["rows"]
    reference = f"AASHTO Table 3-{8 + MAX_RATES.index(maximum)}; §3.3.5.1"
    if radius >= rows[0][col]:
        return (
            0.0,
            "normal",
            {"reference": reference, "mode": "published_table_lookup", "row": "NC"},
        )
    if radius >= rows[1][col]:
        return (
            normal,
            "reverse",
            {"reference": reference, "mode": "published_table_lookup", "row": "RC"},
        )
    if radius < rows[-1][col]:
        raise ValueError(
            f"Radius {radius:g} ft is below Table 3-{8 + MAX_RATES.index(maximum)} minimum {rows[-1][col]} ft."
        )
    # Rows increase in e: the first qualifying radius applies, including rounded ties.
    # §3.3.5's published example: 50 mph, emax=8%, R=1870 ft uses R=1830 ft, e=5.4%.
    for row in rows[2:]:
        if radius >= row[col]:
            return (
                row[0] / 100,
                "full",
                {
                    "reference": f"AASHTO Table 3-{8 + MAX_RATES.index(maximum)}; §3.3.5",
                    "mode": "published_table_lookup",
                    "row": row[0],
                    "selection_method": "next_smaller_tabulated_radius",
                    "input_radius_ft": radius,
                    "selected_row_radius_ft": row[col],
                    "selection": (
                        f"R={radius:g} ft uses tabulated R={row[col]:g} ft at e={row[0]:g}%; "
                        "first qualifying row in increasing rate order (§3.3.5); no interpolation."
                    ),
                },
            )
    raise ValueError("No applicable AASHTO radius row was found.")


def check_radius(pack: dict, maximum: int, speed: float, radius: float) -> None:
    """Validate a manual-rate radius against the reviewed table's speed and minimum."""
    rate(pack, maximum, speed, radius, 0.02)
