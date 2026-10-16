"""One local save implementation for both video and GIF exports."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading


class SaveError(Exception):
    def __init__(self, message, code='save_failed'):
        super().__init__(message)
        self.code = code


def native_folder_picker(initial=''):
    # The chosen path comes from the OS dialog, never from a website-supplied path.
    if sys.platform == 'darwin':
        script = '''function run(argv) {
            ObjC.import('AppKit');
            var app = $.NSApplication.sharedApplication;
            app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
            var panel = $.NSOpenPanel.openPanel;
            panel.canChooseDirectories = true;
            panel.canChooseFiles = false;
            panel.allowsMultipleSelection = false;
            panel.canCreateDirectories = true;
            panel.title = '选择保存视频和 GIF 的文件夹';
            panel.prompt = '选择此文件夹';
            if (argv[0]) panel.directoryURL = $.NSURL.fileURLWithPath(argv[0]);
            app.activateIgnoringOtherApps(true);
            return panel.runModal == $.NSModalResponseOK ? panel.URL.path.js : '';
        }'''
        args = ['/usr/bin/osascript', '-l', 'JavaScript', '-e', script, initial]
    else:
        script = '''import sys, tkinter as tk
from tkinter import filedialog
root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
print(filedialog.askdirectory(title='选择保存视频和 GIF 的文件夹', initialdir=sys.argv[1] or None))
root.destroy()
'''
        args = [sys.executable, '-c', script, initial]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise SaveError('选择文件夹超时，请重新点击保存位置。')
    if result.returncode:
        raise SaveError('无法打开系统文件夹窗口，请确认本地服务在桌面环境中运行。')
    return result.stdout.rstrip('\r\n') or None


VIDEO_EXTENSIONS = ('mp4', 'mov', 'm4v', 'webm', 'mkv', 'avi', 'flv', 'wmv', 'ts', 'mpg', 'mpeg', '3gp')


def native_file_picker(initial=''):
    """Open the OS file dialog for a local video; the path never comes from the page."""
    if sys.platform == 'darwin':
        script = '''function run(argv) {
            ObjC.import('AppKit');
            var app = $.NSApplication.sharedApplication;
            app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
            var panel = $.NSOpenPanel.openPanel;
            panel.canChooseDirectories = false;
            panel.canChooseFiles = true;
            panel.allowsMultipleSelection = false;
            panel.allowedFileTypes = $(argv[1].split(','));
            panel.title = '选择要导入的本地视频';
            panel.prompt = '导入';
            if (argv[0]) panel.directoryURL = $.NSURL.fileURLWithPath(argv[0]);
            app.activateIgnoringOtherApps(true);
            return panel.runModal == $.NSModalResponseOK ? panel.URL.path.js : '';
        }'''
        args = ['/usr/bin/osascript', '-l', 'JavaScript', '-e', script, initial, ','.join(VIDEO_EXTENSIONS)]
    else:
        script = '''import sys, tkinter as tk
from tkinter import filedialog
root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
types=[('视频文件',' '.join('*.'+e for e in sys.argv[2].split(',')))]
print(filedialog.askopenfilename(title='选择要导入的本地视频', initialdir=sys.argv[1] or None, filetypes=types))
root.destroy()
'''
        args = [sys.executable, '-c', script, initial, ','.join(VIDEO_EXTENSIONS)]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise SaveError('选择文件超时，请重新点击导入本地文件。')
    if result.returncode:
        raise SaveError('无法打开系统文件窗口，请确认本地服务在桌面环境中运行。')
    return result.stdout.rstrip('\r\n') or None


class ExportStore:
    def __init__(self, state_file, picker=native_folder_picker):
        self.state_file = Path(state_file)
        self.picker = picker
        self.lock = threading.RLock()
        self.picker_lock = threading.Lock()
        try:
            self.state = json.loads(self.state_file.read_text())
            if not isinstance(self.state, dict): raise ValueError()
        except (OSError, ValueError):
            self.state = {}

    def _persist(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.state_file.parent, delete=False) as f:
            temp = Path(f.name)
            json.dump(self.state, f, ensure_ascii=False)
        try:
            os.replace(temp, self.state_file)
        finally:
            temp.unlink(missing_ok=True)

    def location(self):
        with self.lock:
            value = self.state.get('folder')
            path = Path(value) if isinstance(value, str) and value else None
            return {'path': str(path) if path else '', 'name': path.name if path else '',
                    'valid': bool(path and path.is_dir())}

    def choose(self):
        if not self.picker_lock.acquire(blocking=False):
            raise SaveError('文件夹选择窗口已经打开，请先完成选择。')
        try:
            location = self.location()
            chosen = self.picker(location['path'] if location['valid'] else '')
            if not chosen:
                return {**self.location(), 'cancelled': True}
            path = Path(chosen).resolve()
            if not path.is_dir():
                raise SaveError('找不到指定的位置，请重新设置保存文件夹。', 'folder_missing')
            with self.lock:
                previous = self.state.copy()
                self.state['folder'] = str(path)
                try: self._persist()
                except OSError:
                    self.state = previous
                    raise SaveError('无法记住保存位置，请检查本地服务目录的写入权限。')
            return self.location()
        finally:
            self.picker_lock.release()

    def save(self, source, input_name, kind):
        source = Path(source)
        ext = source.suffix.lower()
        if kind not in ('video', 'gif') or ext not in ('.mp4', '.webm', '.mkv', '.mov', '.gif', '.avi', '.flv', '.m4v'):
            raise SaveError('请选择已经生成的视频或 GIF。')
        if not source.is_file():
            raise SaveError('生成的文件已失效，请重新获取视频。')
        value = input_name.strip()
        if len(input_name) > 100 or re.search(r'[\\/:*?"<>|\x00-\x1f]', input_name) or re.fullmatch(r'\.+', value) or (value and input_name[-1] in '. '):
            raise SaveError('请使用有效的文件名，避免 / : 等特殊字符，长度不超过 100 个字。')
        custom = re.sub(r'\.(mp4|webm|mkv|mov|gif|avi|flv|m4v)$', '', value, flags=re.I)
        if value and not custom:
            raise SaveError('请输入文件名称，或留空自动命名。')
        with self.lock:
            location = self.location()
            if not location['path']:
                raise SaveError('请先选择保存文件夹。')
            if not location['valid']:
                raise SaveError('找不到指定的位置，请重新设置保存文件夹。', 'folder_missing')
            folder = Path(location['path'])
            counter = self.state.get('next', 1)
            if not isinstance(counter, int) or counter < 1: counter = 1
            created = False
            try:
                while True:
                    name = custom + ext if custom else f'拾片下载{"动图" if kind == "gif" else "视频"} {counter:02d}{ext}'
                    target = folder / name
                    try:
                        output = target.open('xb')
                        created = True
                        break
                    except FileExistsError:
                        if custom: raise SaveError('同名文件已存在，请修改文件名后再保存。')
                        counter += 1
                with output, source.open('rb') as original:
                    shutil.copyfileobj(original, output)
                    output.flush()
                    os.fsync(output.fileno())
                if not custom:
                    self.state['next'] = counter + 1
                    self._persist()
                return {'path': str(target), 'filename': name, 'size': target.stat().st_size,
                        'folder': self.location()}
            except Exception as error:
                if created: target.unlink(missing_ok=True)
                if isinstance(error, SaveError): raise
                if isinstance(error, FileNotFoundError) and not folder.is_dir():
                    raise SaveError('找不到指定的位置，请重新设置保存文件夹。', 'folder_missing') from error
                if isinstance(error, PermissionError):
                    raise SaveError('无法写入这个文件夹，请更换保存位置或检查系统权限。') from error
                raise SaveError('保存未完成，请检查磁盘空间并重试。') from error
