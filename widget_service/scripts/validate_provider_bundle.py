#!/usr/bin/env python3
"""Validate one CLI Provider Bundle and print its compiled Template summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "cloud"))


def main() -> int:
    from services.cardplan_template.provider_bundle import load_provider_bundle

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Directory containing provider.json")
    args = parser.parse_args()
    bundle = load_provider_bundle(args.bundle)
    summary = {
        "providerId": bundle.manifest.provider_id,
        "providerVersion": bundle.manifest.provider_version,
        "bundleDigest": bundle.bundle_digest,
        "capabilities": [
            {
                "capabilityId": capability.capability_id,
                "dataSchema": capability.data_schema.model_dump(by_alias=True),
            }
            for capability in bundle.manifest.capabilities
        ],
        "templates": [
            {
                "templateId": definition.wire_id,
                "capabilityId": definition.capability_id,
                "variants": [variant.size for variant in definition.variants],
            }
            for definition in bundle.templates
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
