import subprocess
import sys


def test_cli_runs_complete_journey():
    result = subprocess.run(
        [sys.executable, "-m", "apps.runtime.run", "--order", "ORD-8842"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    expected_in_order = [
        "Inventory Agent",
        "Dispatch Agent",
        "Carrier Agent",
        "Customer Communications Agent",
    ]
    positions = [result.stdout.index(label) for label in expected_in_order]
    assert positions == sorted(positions)
    assert "500 kg" in result.stdout
    assert "VEH-COLD-01" in result.stdout
    assert "CARRIER-COLD-01" in result.stdout
    assert "INR 900" in result.stdout
    assert "Run status: COMPLETED" in result.stdout


def test_cli_unknown_order_returns_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "apps.runtime.run", "--order", "UNKNOWN"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "ORDER_NOT_FOUND" in result.stderr
