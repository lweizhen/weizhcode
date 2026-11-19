from dataclasses import replace
import os

import pytest


@pytest.mark.parametrize('value', ['../escape', '/tmp/a', 'C:\\secret', 'CON', 'a:b', '.', '..', 'x/../y', '', 'a'*33])
def test_ctx_t17_ids_cannot_control_paths(value):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchivePaths

    paths = ArchivePaths('20261118T000000-' + 'a'*32)
    with pytest.raises(ArchiveFailure):
        paths.object(value)


def test_ctx_t17_lazy_inspection_and_native_pins(isolated_context):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard, ArchivePaths, new_record_id
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    paths = ArchivePaths('20261118T000000-' + 'a'*32)
    record = new_record_id()
    guard = ArchiveGuard(make_root(root))
    with guard.pin_target(paths.object(record)) as target:
        assert not target.exists and target.path.is_relative_to(root)
        assert target.nearest_existing == root
        target.verify()
    assert not (root / '.weizhcode').exists()
    with pytest.raises(ArchiveFailure, match='保护已结束'):
        target.verify()
    (root / 'folder').mkdir()
    (root / 'folder' / 'sample').write_text('safe')
    with guard.pin_target(('folder', 'sample')) as target:
        assert target.exists and target.identity is not None
        target.verify()


def test_ctx_t17_changed_root_and_rng_fail_closed(isolated_context, monkeypatch):
    import weizhcode.compact.archive_fs as fs
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    identity = make_root(root)
    with pytest.raises(fs.ArchiveFailure):
        with fs.ArchiveGuard(replace(identity, identity=(0, 0))).pin_target(('a',)):
            pytest.fail('不应进入已改变的根')
    def unavailable():
        raise OSError('synthetic RNG failure')
    monkeypatch.setattr(fs, 'uuid4', unavailable)
    with pytest.raises(fs.ArchiveFailure, match='身份'):
        fs.new_record_id()
    assert not (root / '.weizhcode').exists()


def test_ctx_t17_link_escape_is_rejected(isolated_context):
    from weizhcode.compact.archive_fs import ArchiveGuard, ArchiveFailure
    from weizhcode.permissions.sandbox import make_root

    root, home = isolated_context
    try:
        (root / 'link').symlink_to(home, target_is_directory=True)
    except OSError:
        pytest.skip('原生符号链接不可创建；junction专项另测')
    with pytest.raises(ArchiveFailure):
        with ArchiveGuard(make_root(root)).pin_target(('link', 'secret')):
            pytest.fail('不应跟随链接')


@pytest.mark.skipif(os.name != 'nt', reason='Windows原生junction')
def test_ctx_t17_windows_junction_is_rejected(isolated_context):
    import subprocess
    from weizhcode.compact.archive_fs import ArchiveGuard, ArchiveFailure
    from weizhcode.permissions.sandbox import make_root

    root, home = isolated_context
    link = root / 'junction'
    command = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(home)], capture_output=True, timeout=5)
    if command.returncode:
        pytest.skip('本机不能创建junction')
    try:
        with pytest.raises(ArchiveFailure):
            with ArchiveGuard(make_root(root)).pin_target(('junction', 'secret')):
                pytest.fail('不应跟随junction')
    finally:
        link.rmdir()  # 只移除本测试创建的链接，绝不递归移除目标。


@pytest.mark.parametrize('parts', [('../x',), ('C:',), ('a/b',), ('CON.txt',), ('name.',), ('name ',), ()])
def test_ctx_t17_invalid_relative_forms_are_rejected(isolated_context, parts):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    with pytest.raises(ArchiveFailure):
        with ArchiveGuard(make_root(root)).pin_target(parts):
            pytest.fail('不应接受非法相对组件')


def test_ctx_t17_missing_target_changed_during_operation(isolated_context):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    with pytest.raises(ArchiveFailure, match='已变化'):
        with ArchiveGuard(make_root(root)).pin_target(('new', 'record')) as target:
            (root / 'new').mkdir()
            target.verify()


@pytest.mark.skipif(os.name != 'nt', reason='Windows句柄固定原生行为')
def test_ctx_t17_windows_open_handle_blocks_replacement(isolated_context):
    from weizhcode.compact.archive_fs import ArchiveGuard
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    folder = root / 'fixed'
    folder.mkdir()
    with ArchiveGuard(make_root(root)).pin_target(('fixed',), directory=True) as target:
        with pytest.raises(OSError):
            folder.rename(root / 'moved')
        target.verify()
    folder.rename(root / 'moved')
    assert (root / 'moved').is_dir()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX目录句柄原生行为')
def test_ctx_t17_posix_pinned_directory_detects_replacement(isolated_context):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    folder = root / 'fixed'
    folder.mkdir()
    with pytest.raises(ArchiveFailure):
        with ArchiveGuard(make_root(root)).pin_target(('fixed',), directory=True) as target:
            assert target.parent_fd is not None
            folder.rename(root / 'moved')
            folder.mkdir()
            target.verify()


def test_ctx_t18_exclusive_safe_text_and_publication(isolated_context):
    import hashlib
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard, publish_exclusive, write_exclusive
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    (root / 'pending').mkdir()
    (root / 'objects').mkdir()
    guard = ArchiveGuard(make_root(root))
    text = '\ufeff原话\r\n保留\x1b控制字符与换行\n'
    saved = write_exclusive(guard, ('pending', 'raw.txt'), text, kind='human')
    assert saved.sha256 == hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert saved.safe_bytes == len(text.encode('utf-8'))
    publish_exclusive(guard, ('pending', 'raw.txt'), ('objects', 'raw.txt'), expected=saved)
    assert (root / 'objects/raw.txt').read_bytes() == text.encode('utf-8')
    with pytest.raises(ArchiveFailure, match='已存在'):
        write_exclusive(guard, ('pending', 'raw.txt'), '不能覆盖', kind='human')
    with pytest.raises(ArchiveFailure, match='已存在'):
        publish_exclusive(guard, ('pending', 'raw.txt'), ('objects', 'raw.txt'), expected=saved)
    assert (root / 'objects/raw.txt').read_bytes() == text.encode('utf-8')


@pytest.mark.parametrize('kind,limit', [('human', 8*1024*1024), ('tool', 2*1024*1024), ('metadata', 64*1024)])
def test_ctx_t18_record_limits_do_not_save_prefix(isolated_context, kind, limit):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard, write_exclusive
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    guard = ArchiveGuard(make_root(root))
    saved = write_exclusive(guard, ('at-limit',), 'x' * limit, kind=kind)
    assert saved.safe_bytes == limit
    with pytest.raises(ArchiveFailure, match='上限'):
        write_exclusive(guard, ('large',), 'x' * (limit+1), kind=kind)
    assert not (root / 'large').exists()


def test_ctx_t18_failed_write_leaves_honest_partial_and_bad_source_not_published(isolated_context, monkeypatch):
    import weizhcode.compact.archive_fs as fs
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    guard = fs.ArchiveGuard(make_root(root))
    def full(*args):
        raise OSError('synthetic disk full')
    with monkeypatch.context() as patch:
        patch.setattr(fs.os, 'write', full)
        with pytest.raises(fs.ArchiveFailure):
            fs.write_exclusive(guard, ('partial',), '原话', kind='human')
    assert (root / 'partial').exists()  # 不虚称文件提交被完整撤销。
    saved = fs.write_exclusive(guard, ('good',), 'original', kind='human')
    (root / 'good').write_text('changed')
    with pytest.raises(fs.ArchiveFailure):
        fs.publish_exclusive(guard, ('good',), ('must-not-exist',), expected=saved)
    assert not (root / 'must-not-exist').exists()


def test_ctx_t18_published_but_unverified_is_uncertain(isolated_context, monkeypatch):
    from contextlib import contextmanager
    import weizhcode.compact.archive_fs as fs
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    guard = fs.ArchiveGuard(make_root(root))
    saved = fs.write_exclusive(guard, ('staged',), 'safe text', kind='human')
    original = guard.pin_target
    @contextmanager
    def failed_verification(parts, **kwargs):
        if parts == ('published',):
            raise fs.ArchiveFailure()
        with original(parts, **kwargs) as pinned:
            yield pinned
    monkeypatch.setattr(guard, 'pin_target', failed_verification)
    with pytest.raises(fs.ArchiveFailure) as caught:
        fs.publish_exclusive(guard, ('staged',), ('published',), expected=saved)
    assert caught.value.code == 'ARCHIVE_COMMIT_UNCERTAIN'
    assert (root / 'published').read_text() == 'safe text'


def test_ctx_t19_view_preserves_exact_text_and_splits_long_lines():
    import hashlib
    import json
    from weizhcode.compact.archive_fs import encode_view

    text = '\ufeff' + '中文\r\n\x1b' * 1000 + 'x' * 5000
    view = encode_view(text)
    parts = [json.loads(line) for line in view.splitlines()]
    assert ''.join(part['text'] for part in parts) == text
    assert all(len(part['text']) <= 1024 for part in parts)
    assert [part['part'] for part in parts] == list(range(1, len(parts)+1))
    assert hashlib.sha256(view.encode()).digest() != hashlib.sha256(text.encode()).digest()


def test_ctx_t19_user_pages_and_summary_are_bounded():
    import json
    from weizhcode.compact.archive_fs import ArchivePaths, encode_user_pages, index_summary
    from weizhcode.compact.contracts import ArchiveRef

    paths = ArchivePaths('20261118T000000-' + 'a'*32)
    records = [(i, ArchiveRef(paths.session_id, f'{i:032x}', 'human', f'user-{i}', 'a'*64,
        10, 'objects/' + 'x'*600, 'views/' + 'x'*600, 'b'*64, True)) for i in range(1, 1001)]
    pages = encode_user_pages(records)
    items = [json.loads(line) for page in pages for line in page.text.splitlines()]
    assert [item['seq'] for item in items] == list(range(1, 1001))
    assert all(len(page.text.encode()) <= 256*1024 and len(page.text.splitlines()) <= 256 for page in pages)
    summary = index_summary(paths, pages)
    assert len(summary) <= 2048 and '1000' in summary and 'page-1.jsonl' in summary
    assert 'objects/' not in summary


def test_ctx_t19_bad_index_does_not_silently_renumber():
    from weizhcode.compact.archive_fs import ArchiveFailure, encode_user_pages
    with pytest.raises(ArchiveFailure):
        encode_user_pages([(2, None), (1, None)])


def test_ctx_t20_git_ignored_untracked_and_non_git(isolated_context):
    import subprocess
    from weizhcode.compact.archive_fs import ArchiveFailure, require_ignored

    root, _ = isolated_context
    paths = [('.weizhcode', 'sessions', 'sample', 'objects', 'raw.txt'),
             ('.weizhcode', 'sessions', 'sample', '.pending', 'raw.txt')]
    require_ignored(root, paths)
    subprocess.run(['git', 'init', '-q', str(root)], check=True, timeout=5)
    with pytest.raises(ArchiveFailure, match='忽略'):
        require_ignored(root, paths)
    assert not (root / '.gitignore').exists()
    (root / '.gitignore').write_text('.weizhcode/sessions/\n')
    require_ignored(root, paths)
    target = root.joinpath(*paths[0])
    target.parent.mkdir(parents=True)
    target.write_text('synthetic')
    subprocess.run(['git', '-C', str(root), 'add', '-f', '--', str(target)], check=True, timeout=5)
    with pytest.raises(ArchiveFailure, match='跟踪'):
        require_ignored(root, paths)
    assert (root / '.gitignore').read_text() == '.weizhcode/sessions/\n'


def test_ctx_t24_owned_cleanup_never_deletes_unregistered_objects(isolated_context):
    from dataclasses import replace
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard, ArchivePaths, cleanup_owned, ensure_directories, write_exclusive
    from weizhcode.permissions.sandbox import make_root

    root, _ = isolated_context
    guard = ArchiveGuard(make_root(root))
    paths = ArchivePaths('20261118T000000-' + 'a'*32)
    staging = paths.pending('b'*32)
    ensure_directories(guard, staging)
    saved = write_exclusive(guard, (*staging, 'raw'), 'synthetic', kind='human')
    (root / 'neighbor').write_text('must remain')
    with pytest.raises(ArchiveFailure):
        cleanup_owned(guard, replace(saved, identity=(0, 0)))
    assert root.joinpath(*saved.parts).exists()
    cleanup_owned(guard, saved)
    assert not root.joinpath(*saved.parts).exists()
    assert (root / 'neighbor').read_text() == 'must remain'
