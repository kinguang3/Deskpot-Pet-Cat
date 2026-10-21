"""数据存储模块

负责持久化存储宠物状态、设置、互动记录。
使用 JSON 文件存储。

数据目录位于用户数据目录（%APPDATA%/GBC Nina/data），
不写在程序安装目录里，因此装到 C:\\Program Files 也能正常读写。
"""

import json
from pathlib import Path

from src.utils.logger import get_logger
from src.utils import json_io, paths

logger = get_logger(__name__)


class Storage:
    """简单的 JSON 文件存储。"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = str(paths.data_path())

        self._data_dir = Path(data_dir)
        self._available = True

        # 建目录失败不能让程序起不来：降级为「不持久化」，
        # 桌宠仍可正常运行，只是这次不保存记忆。
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._available = False
            logger.error(
                "Data dir %s unavailable; running without persistence",
                self._data_dir,
                exc_info=True,
            )

        # 旧版本把 data/（互动记忆等）写在安装目录里。装进 Program Files
        # 后那里不可写，等于永久丢失记忆。此处把旧文件一次性迁移过来，
        # 只复制目标不存在的文件，幂等、绝不覆盖新数据。
        if self._available:
            try:
                paths.migrate_legacy_user_data()
            except Exception:
                logger.warning(
                    "Legacy data migration skipped due to error",
                    exc_info=True,
                )

        self._cache: dict[str, dict] = {}
        logger.debug(
            "Storage initialized (dir: %s, available: %s)",
            self._data_dir,
            self._available,
        )

    def _get_file_path(self, name: str) -> Path:
        return self._data_dir / f"{name}.json"

    def load(self, name: str = "pet_data") -> dict:
        """加载数据。

        损坏的 JSON 不会静默清空：先尝试回退到 ``.bak`` 备份，再把损坏
        文件隔离为 ``.corrupt``，避免用户数据被默认值覆盖。
        """
        path = self._get_file_path(name)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[name] = json.load(f)
                logger.debug("Data loaded: %s", name)
            except json.JSONDecodeError:
                logger.error("Failed to parse data file: %s", path.name)
                self._cache[name] = json_io.recover_with_backup(
                    path, label="data"
                )
            except OSError:
                logger.error("Failed to read data file: %s", path.name)
                self._cache[name] = {}
        else:
            self._cache[name] = {}
            logger.debug("Data file not found, using empty: %s", name)
        return self._cache[name]

    def save(self, data: dict, name: str = "pet_data") -> bool:
        """原子化保存数据。

        实现见 :func:`src.utils.json_io.atomic_write_json`：写临时文件 ->
        fsync -> os.replace，避免崩溃/断电产生截断的非法 JSON。
        """
        path = self._get_file_path(name)
        ok = json_io.atomic_write_json(
            path, data, label="data", strict_backup=True
        )
        if ok:
            self._cache[name] = data
        return ok
