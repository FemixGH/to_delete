import argparse
import os
import socket
import sys
import threading
import time
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List
import importlib.util

from yandex_openai_proxy import run_proxy


def wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def collect_candidate_paths(workdir: Path, run_dir: Path) -> List[Path]:
    candidates: List[Path] = []

    # Типичные директории/файлы
    for name in [
        'deepteam_runs',
        'deepteam_output',
        'experiments',
    ]:
        p = workdir / name
        if p.exists():
            candidates.append(p)

    # Всё, что содержит deepteam в названии
    for p in workdir.iterdir():
        if 'deepteam' in p.name.lower():
            candidates.append(p)

    # Текущая директория запуска
    candidates.append(run_dir)

    # Дедупликация
    uniq = []
    seen = set()
    for p in candidates:
        if p.exists():
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                uniq.append(p)
    return uniq


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Запуск тестов DeepTeam (confident-ai/deepteam) против YandexGPT через локальный OpenAI-прокси. '
            'Скрипт поднимает прокси, запускает deepteam с вашими аргументами и упаковывает результаты в ZIP.'
        )
    )

    parser.add_argument('--proxy-host', default='127.0.0.1', help='Хост локального прокси OpenAI')
    parser.add_argument('--proxy-port', type=int, default=8001, help='Порт локального прокси OpenAI')
    parser.add_argument('--openai-api-key', default='sk-dummy', help='Ключ OpenAI (фиктивный, для совместимости)')
    parser.add_argument('--timeout', type=float, default=30.0, help='Таймаут ожидания старта прокси, сек')

    parser.add_argument('--results-root', default='deepteam_runs', help='Корневая папка для результатов запуска')
    parser.add_argument('--zip-path', default=None, help='Путь к итоговому zip; по умолчанию создаётся автоматически')

    parser.add_argument('deepteam_args', nargs=argparse.REMAINDER,
                        help='Аргументы, которые будут напрямую переданы CLI deepteam (начните с "--" перед первыми аргументами)')

    args = parser.parse_args()

    # Проверка наличия пакета deepteam (как маркера установленности)
    if importlib.util.find_spec('deepteam') is None:
        print('Ошибка: пакет "deepteam" не установлен. Установите его (см. репозиторий confident-ai/deepteam) и повторите попытку.', file=sys.stderr)
        return 3

    workdir = Path.cwd()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_root = workdir / args.results_root
    run_dir = results_root / f'run_{timestamp}'
    ensure_dir(run_dir)

    # Запуск прокси
    proxy_thread = threading.Thread(target=run_proxy, kwargs={'host': args.proxy_host, 'port': args.proxy_port}, daemon=True)
    proxy_thread.start()

    if not wait_port(args.proxy_host, args.proxy_port, timeout=args.timeout):
        print(f'Ошибка: прокси не поднялся на {args.proxy_host}:{args.proxy_port} за {args.timeout} сек', file=sys.stderr)
        return 2

    # Окружение для OpenAI-совместимых клиентов
    env = os.environ.copy()
    base_url = f'http://{args.proxy_host}:{args.proxy_port}/v1'
    env['OPENAI_API_KEY'] = args.openai_api_key
    env['OPENAI_API_BASE'] = base_url
    env['OPENAI_BASE'] = base_url
    env['OPENAI_BASE_URL'] = base_url

    # Команда DeepTeam: предпочтительно – консольный скрипт 'deepteam'
    if shutil.which('deepteam'):
        cmd = ['deepteam']
    else:
        # Резервный запуск: некоторые сборки могут поддерживать модульный вызов
        cmd = [sys.executable, '-m', 'deepteam']

    if not args.deepteam_args:
        # Если не передали аргументы — покажем справку deepteam
        cmd.append('--help')
    else:
        da = args.deepteam_args
        if da and da[0] == '--':
            da = da[1:]
        cmd.extend(da)

    stdout_path = run_dir / 'deepteam_stdout.txt'
    stderr_path = run_dir / 'deepteam_stderr.txt'

    print('Запуск deepteam с аргументами:', ' '.join(cmd))
    with open(stdout_path, 'w', encoding='utf-8') as out, open(stderr_path, 'w', encoding='utf-8') as err:
        proc = subprocess.Popen(cmd, stdout=out, stderr=err, env=env, cwd=workdir)
        retcode = proc.wait()

    if retcode != 0:
        print(f'ВНИМАНИЕ: deepteam завершился с кодом {retcode}. Подробности см. в {stderr_path.name}')

    # Сбор артефактов и упаковка
    include_paths = collect_candidate_paths(workdir, run_dir)

    if args.zip_path:
        zip_path = Path(args.zip_path)
        if zip_path.suffix.lower() != '.zip':
            zip_path = zip_path.with_suffix('.zip')
    else:
        zip_path = workdir / f'deepteam_report_{timestamp}.zip'

    zip_stage = run_dir / 'zip_stage'
    ensure_dir(zip_stage)

    for src in include_paths:
        if not src.exists():
            continue
        # Избегаем рекурсии: не копируем источники, которые включают zip_stage внутри
        try:
            if str((zip_stage).resolve()).startswith(str(src.resolve())):
                continue
        except Exception:
            pass
        dst = zip_stage / src.name
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                ensure_dir(dst.parent)
                shutil.copy2(src, dst)
        except Exception as e:
            print(f'Предупреждение: не удалось добавить {src}: {e}', file=sys.stderr)

    # Явно добавим логи
    logs_dst = zip_stage / 'run_logs'
    ensure_dir(logs_dst)
    for name in ['deepteam_stdout.txt', 'deepteam_stderr.txt']:
        p = run_dir / name
        if p.exists():
            try:
                shutil.copy2(p, logs_dst / name)
            except Exception as e:
                print(f'Предупреждение: не удалось скопировать лог {p}: {e}', file=sys.stderr)

    base_name = str(zip_path.with_suffix(''))
    shutil.make_archive(base_name, 'zip', root_dir=zip_stage)

    print(f'Готово. Итоговый архив: {zip_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
