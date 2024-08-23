import argparse
import shutil


# 复制目录
def copy_tree(src, dst):
    shutil.copytree(src, dst)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='for test')
    parser.add_argument('--src', type=str, help='', default='')
    parser.add_argument('--dst', type=str, help='', default='')
    args = parser.parse_args()
    copy_tree(args.src, args.dst)
