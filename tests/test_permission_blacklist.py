import pytest

from weizhcode.permissions.blacklist import hits_blacklist


@pytest.mark.parametrize("command", ["rm -rf /", "rm -fr ~", "rm -r -f $HOME", "rm --recursive --force /*",
    "dd if=/dev/zero of=/dev/sda", "mkfs.ext4 /dev/x", ":(){ :|:& };:", "echo x > /dev/nvme0n1"])
def test_posix(command):
    assert hits_blacklist(command)


@pytest.mark.parametrize("command", ["Remove-Item -Recurse -Force C:\\", "rm -rf C:\\",
    "rd /s /q C:\\", "Clear-Disk -Number 0", "format C:", "Format-Volume -DriveLetter D"])
def test_windows(command):
    assert hits_blacklist(command)


@pytest.mark.parametrize("command", ["git status", "rm -rf ./build/", "rm -rf /project/build", r"Remove-Item -Recurse -Force C:\project\build"])
def test_posix_windows_safe(command):
    assert hits_blacklist(command) is None


def test_posix_large_input():
    assert hits_blacklist("git " + "a " * 100000) is None
    assert hits_blacklist("rm -rf " + "a" * 100000 + "/project") is None
