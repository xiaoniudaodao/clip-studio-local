import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from export_storage import ExportStore, SaveError


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / '保存视频的文件夹'
        self.folder.mkdir()
        self.original = self.root / 'original.mp4'
        self.original.write_bytes(b'actual video bytes')
        self.state_file = self.root / 'settings.json'
        self.store = ExportStore(self.state_file, picker=lambda initial: str(self.folder))
        self.store.choose()

    def tearDown(self):
        self.temp.cleanup()

    def test_folder_path_and_counter_survive_restart(self):
        first = self.store.save(self.original, '', 'video')
        self.assertEqual(first['filename'], '拾片下载视频 01.mp4')
        restored = ExportStore(self.state_file)
        self.assertEqual(restored.location()['path'], str(self.folder.resolve()))
        self.assertTrue(restored.location()['valid'])
        self.assertEqual(restored.save(self.original, '', 'video')['filename'], '拾片下载视频 02.mp4')

    def test_ten_saves_skip_existing_file_and_copy_exact_bytes(self):
        (self.folder / '拾片下载视频 01.mp4').write_bytes(b'keep original')
        names = [self.store.save(self.original, '', 'video')['filename'] for _ in range(10)]
        self.assertEqual(names[0], '拾片下载视频 02.mp4')
        self.assertEqual(names[-1], '拾片下载视频 11.mp4')
        self.assertEqual(len(set(names)), 10)
        self.assertEqual((self.folder / '拾片下载视频 01.mp4').read_bytes(), b'keep original')
        self.assertEqual((self.folder / names[-1]).read_bytes(), self.original.read_bytes())

    def test_custom_collision_does_not_overwrite(self):
        (self.folder / '我的视频.mp4').write_bytes(b'original')
        with self.assertRaisesRegex(SaveError, '同名文件已存在'):
            self.store.save(self.original, '我的视频', 'video')
        self.assertEqual((self.folder / '我的视频.mp4').read_bytes(), b'original')

    def test_video_and_gif_share_save_location_and_counter(self):
        self.store.save(self.original, '', 'video')
        gif = self.root / 'clip.gif'
        gif.write_bytes(b'GIF89a')
        result = self.store.save(gif, '', 'gif')
        self.assertEqual(result['filename'], '拾片下载动图 02.gif')
        self.assertEqual(result['path'], str(self.folder.resolve() / '拾片下载动图 02.gif'))
        self.assertEqual(Path(result['path']).read_bytes(), gif.read_bytes())

    def test_deleted_folder_is_reported_and_can_be_replaced(self):
        self.folder.rmdir()
        self.assertFalse(self.store.location()['valid'])
        with self.assertRaises(SaveError) as caught:
            self.store.save(self.original, '', 'video')
        self.assertEqual(caught.exception.code, 'folder_missing')
        self.assertIn('找不到指定的位置', str(caught.exception))
        replacement = self.root / '新位置'
        replacement.mkdir()
        self.store.picker = lambda initial: str(replacement)
        self.assertEqual(self.store.choose()['path'], str(replacement.resolve()))
        self.assertTrue(Path(self.store.save(self.original, '', 'video')['path']).is_file())

    def test_cancelled_picker_preserves_selected_path(self):
        self.store.picker = lambda initial: None
        result = self.store.choose()
        self.assertTrue(result['cancelled'])
        self.assertEqual(result['path'], str(self.folder.resolve()))

    def test_partial_copy_failure_removes_only_new_file(self):
        (self.folder / '已有视频.mp4').write_bytes(b'keep')
        with patch('export_storage.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(SaveError, '保存未完成'):
                self.store.save(self.original, '失败视频', 'video')
        self.assertFalse((self.folder / '失败视频.mp4').exists())
        self.assertEqual((self.folder / '已有视频.mp4').read_bytes(), b'keep')

    def test_concurrent_downloads_use_unique_names(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: self.store.save(self.original, '', 'video'), range(8)))
        self.assertEqual(len(set(r['filename'] for r in results)), 8)
        self.assertEqual(len(list(self.folder.glob('拾片下载视频 *.mp4'))), 8)

    def test_unsafe_names_cannot_write_outside_selected_folder(self):
        for value in ('../escape', '..', 'name.', 'name\x00', '.mp4'):
            with self.assertRaises(SaveError):
                self.store.save(self.original, value, 'video')
        self.assertEqual(list(self.folder.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
