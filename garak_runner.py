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

# Локальный OpenAI-совместимый прокси для YandexGPT
from yandex_openai_proxy import run_proxy


def wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                sock.connect((host, port))
                return True
            except OSError:
                time.sleep(0.2)
    return False


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def collect_candidate_paths(workdir: Path) -> List[Path]:
    # Добавляем известные кандидаты, если существуют
    candidates: List[Path] = []

    # Часто встречающиеся директории с результатами garak
    for name in [
        'garak_runs',
        'experiments',
        'garak_output',
    ]:
        p = workdir / name
        if p.exists():
            candidates.append(p)

    # Добавляем директории и файлы, содержащие 'garak' в имени
    for p in workdir.iterdir():
        if 'garak' in p.name.lower():
            candidates.append(p)

    # Убираем дубликаты
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
            'Запуск тестов Garak против YandexGPT через локальный OpenAI-прокси. '
            'Скрипт запускает прокси, затем вызывает garak с переданными аргументами, '
            'и упаковывает результаты в один zip.'
        )
    )

    parser.add_argument('--proxy-host', default='127.0.0.1', help='Хост локального прокси OpenAI')
    parser.add_argument('--proxy-port', type=int, default=8001, help='Порт локального прокси OpenAI')
    parser.add_argument('--openai-api-key', default='sk-dummy', help='Ключ OpenAI (фиктивный, для совместимости)')
    parser.add_argument('--timeout', type=float, default=30.0, help='Таймаут ожидания старта прокси, сек')

    parser.add_argument('--results-root', default='garak_runs', help='Корневая папка для результатов запуска')
    parser.add_argument('--zip-path', default=None, help='Путь к итоговому zip; по умолчанию создаётся автоматически')

    parser.add_argument('garak_args', nargs=argparse.REMAINDER,
                        help='Аргументы, которые будут напрямую переданы CLI garak (начните с "--" перед первыми аргументами garak)')

    args = parser.parse_args()

    # Проверим, установлен ли пакет garak
    if importlib.util.find_spec('garak') is None:
        print('Ошибка: пакет \"garak\" не установлен. Установите зависимости из requirements.txt и повторите попытку.', file=sys.stderr)
        return 3

    # Рабочие пути
    workdir = Path.cwd()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_root = workdir / args.results_root
    run_dir = results_root / f'run_{timestamp}'
    ensure_dir(run_dir)

    # Запуск локального прокси в отдельном потоке
    proxy_thread = threading.Thread(target=run_proxy, kwargs={
        'host': args.proxy_host,
        'port': args.proxy_port,
    }, daemon=True)
    proxy_thread.start()

    if not wait_port(args.proxy_host, args.proxy_port, timeout=args.timeout):
        print(f'Ошибка: прокси не поднялся на {args.proxy_host}:{args.proxy_port} за {args.timeout} сек', file=sys.stderr)
        return 2

    # Переменные окружения для Garak/OpenAI клиента
    env = os.environ.copy()
    base_url = f'http://{args.proxy_host}:{args.proxy_port}/v1'
    # Для разных версий клиентов/плагинов объявим обе переменные
    env['OPENAI_API_KEY'] = args.openai_api_key
    env['OPENAI_API_BASE'] = base_url
    env['OPENAI_BASE'] = base_url

    # Команда для garak
    garak_cmd = [sys.executable, '-m', 'garak']

    # Если пользователь явно не передал аргументов, подставим минимально полезные
    if not args.garak_args:
        default_args = [
            '--help'
        ]
        garak_cmd.extend(default_args)
    else:
        # Убираем ведущий маркер '--' если он есть
        ga = args.garak_args
        if ga and ga[0] == '--':
            ga = ga[1:]
        garak_cmd.extend(ga)

    # Логи
    stdout_path = run_dir / 'garak_stdout.txt'
    stderr_path = run_dir / 'garak_stderr.txt'

    print('Запуск garak с аргументами:', ' '.join(garak_cmd))
    with open(stdout_path, 'w', encoding='utf-8') as out, open(stderr_path, 'w', encoding='utf-8') as err:
        proc = subprocess.Popen(garak_cmd, stdout=out, stderr=err, env=env, cwd=workdir)
        retcode = proc.wait()

    if retcode != 0:
        print(f'ВНИМАНИЕ: garak завершился с кодом {retcode}. Подробности см. в {stderr_path.name}')

    # Сбор результатов и упаковка
    include_paths = collect_candidate_paths(workdir)

    if args.zip_path:
        zip_path = Path(args.zip_path)
        # Без расширения .zip — добавим
        if zip_path.suffix.lower() != '.zip':
            zip_path = zip_path.with_suffix('.zip')
    else:
        zip_path = workdir / f'garak_report_{timestamp}.zip'

    # Создадим временную папку, куда скопируем все кандидаты
    zip_stage = run_dir / 'zip_stage'
    ensure_dir(zip_stage)

    # Скопируем кандидатов
    for src in include_paths:
        if not src.exists():
            continue
        # Пропустим сам run_dir и все источники, которые содержат zip_stage внутри (чтобы избежать рекурсивного копирования)
        try:
            if str(zip_stage.resolve()).startswith(str(src.resolve())):
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

    # Явно добавим логи текущего запуска
    logs_dst = zip_stage / 'run_logs'
    ensure_dir(logs_dst)
    for name in ['garak_stdout.txt', 'garak_stderr.txt']:
        p = run_dir / name
        if p.exists():
            try:
                shutil.copy2(p, logs_dst / name)
            except Exception as e:
                print(f'Предупреждение: не удалось скопировать лог {p}: {e}', file=sys.stderr)

    # Упакуем zip_stage
    base_name = str(zip_path.with_suffix(''))
    shutil.make_archive(base_name, 'zip', root_dir=zip_stage)

    print(f'Готово. Итоговый архив: {zip_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
