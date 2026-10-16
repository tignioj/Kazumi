#!/usr/bin/env python3
"""Sign a test HAP using the installed 小白调试助手's existing local identity."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--config", type=Path,
        default=Path.home() / "Documents/hap_installer/signConfig.json",
    )
    parser.add_argument("--profile", type=Path)
    parser.add_argument(
        "--signer", type=Path,
        default=Path("/Applications/小白调试助手.app/Contents/Frameworks/"
                     "App.framework/Resources/flutter_assets/assets/macos/signer"),
    )
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output must be different files")
    config = json.loads(args.config.read_text())
    with zipfile.ZipFile(args.input) as hap:
        app = json.loads(hap.read("module.json"))["app"]
    profile = args.profile or (
        args.config.parent / "store" /
        (app["bundleName"].replace(".", "_") + ".p7b")
    )
    if not profile.is_file():
        parser.error(f"Create a device profile for {app['bundleName']} first: {profile}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def run(options):
        result = subprocess.run(
            [str(args.signer), *options], capture_output=True, text=True,
        )
        message = result.stdout + result.stderr
        # This signer also reports some failures with exit code zero.
        if result.returncode or f"{options[0]} success" not in message:
            password = config.get("keystorePwd", "")
            if password:
                message = message.replace(password, "<redacted>")
            raise SystemExit(message)

    run([
        "sign-app", "-mode", "localSign", "-keyAlias", config["keyAlias"],
        "-appCertFile", config["certPath"], "-profileFile", str(profile),
        "-signAlg", "SHA256withECDSA", "-keystoreFile", config["keystoreFile"],
        "-keystorePwd", config["keystorePwd"],
        "-inFile", str(args.input), "-outFile", str(args.output),
        "-compatibleVersion", str(app["minAPIVersion"] % 1000), "-signCode", "1",
    ])
    with tempfile.TemporaryDirectory(prefix="kazumi-sign-") as directory:
        run([
            "verify-app", "-inFile", str(args.output),
            "-outCertChain", str(Path(directory) / "chain.cer"),
            "-outProfile", str(Path(directory) / "profile.p7b"),
        ])
    print(f"Signed and verified {app['bundleName']}: {args.output}")


if __name__ == "__main__":
    main()
