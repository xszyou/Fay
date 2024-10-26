#HomeBrew自动安装脚本
#qq 467665317
#brew brew brew brew

#获取硬件信息 判断inter还是苹果M
UNAME_MACHINE="$(uname -m)"
#在X86电脑上测试arm电脑
# UNAME_MACHINE="arm64"

# 判断是Linux还是Mac os
OS="$(uname)"
if [[ "$OS" == "Linux" ]]; then
  HOMEBREW_ON_LINUX=1
elif [[ "$OS" != "Darwin" ]]; then
  echo "Homebrew 只运行在 Mac OS 或 Linux."
fi

# 字符串染色程序
if [[ -t 1 ]]; then
  tty_escape() { printf "\033[%sm" "$1"; }
else
  tty_escape() { :; }
fi
tty_universal() { tty_escape "0;$1"; } #正常显示
tty_mkbold() { tty_escape "1;$1"; } #设置高亮
tty_underline="$(tty_escape "4;39")" #下划线
tty_blue="$(tty_universal 34)" #蓝色
tty_red="$(tty_universal 31)" #红色
tty_green="$(tty_universal 32)" #绿色
tty_yellow="$(tty_universal 33)" #黄色
tty_bold="$(tty_universal 39)" #加黑
tty_cyan="$(tty_universal 36)" #青色
tty_reset="$(tty_escape 0)" #去除颜色

#用户输入极速安装speed，git克隆只取最近新版本
#但是update会出错，提示需要下载全部数据
GIT_SPEED=""

if [[ $0 == "speed" ]]; then
  GIT_SPEED="--depth=1"
else
  for dir in $@; do
      echo $dir
      if [[ $dir == "speed" ]]; then
          GIT_SPEED="--depth=1"
      fi
  done
fi

if [[ $GIT_SPEED != "" ]]; then
echo "${tty_red}
              检测到参数speed，只拉取最新数据，可以正常install使用！
               腾讯和阿里不支持speed拉取，需要腾讯阿里需要完全模式。
          但是以后brew update的时候会报错，运行报错提示的两句命令即可修复
          ${tty_reset}"
fi

#获取前面两个.的数据
major_minor() {
  echo "${1%%.*}.$(x="${1#*.}"; echo "${x%%.*}")"
}

#设置一些平台地址
if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
    #Mac
    if [[ "$UNAME_MACHINE" == "arm64" ]]; then
    #M1
    HOMEBREW_PREFIX="/opt/homebrew"
    HOMEBREW_REPOSITORY="${HOMEBREW_PREFIX}"
    else
    #Inter
    HOMEBREW_PREFIX="/usr/local"
    HOMEBREW_REPOSITORY="${HOMEBREW_PREFIX}/Homebrew"
    fi

    HOMEBREW_CACHE="${HOME}/Library/Caches/Homebrew"
    HOMEBREW_LOGS="${HOME}/Library/Logs/Homebrew"
    
    #国内没有homebrew-services，手动在gitee创建了一个，有少数人用到。
    USER_SERVICES_GIT=https://gitee.com/cunkai/homebrew-services.git

    STAT="stat -f"
    CHOWN="/usr/sbin/chown"
    CHGRP="/usr/bin/chgrp"
    GROUP="admin"
    TOUCH="/usr/bin/touch"

    #获取Mac系统版本
    macos_version="$(major_minor "$(/usr/bin/sw_vers -productVersion)")"
else
  #Linux
  UNAME_MACHINE="$(uname -m)"

  HOMEBREW_PREFIX="/home/linuxbrew/.linuxbrew"
  HOMEBREW_REPOSITORY="${HOMEBREW_PREFIX}/Homebrew"

  HOMEBREW_CACHE="${HOME}/.cache/Homebrew"
  HOMEBREW_LOGS="${HOME}/.logs/Homebrew"

  STAT="stat --printf"
  CHOWN="/bin/chown"
  CHGRP="/bin/chgrp"
  GROUP="$(id -gn)"
  TOUCH="/bin/touch"
fi



#获取系统时间
TIME=$(date "+%Y-%m-%d %H:%M:%S")

JudgeSuccess()
{
    if [ $? -ne 0 ];then
        echo "${tty_red}此步骤失败 '$1'${tty_reset}"
        if [[ "$2" == 'out' ]]; then
          exit 0
        fi
    else
        echo "${tty_green}此步骤成功${tty_reset}"

    fi
}
# 判断是否有系统权限
have_sudo_access() {
  if [[ -z "${HAVE_SUDO_ACCESS-}" ]]; then
    /usr/bin/sudo -l mkdir &>/dev/null
    HAVE_SUDO_ACCESS="$?"
  fi

  if [[ "$HAVE_SUDO_ACCESS" -ne 0 ]]; then
    echo "${tty_red}开机密码输入错误，获取权限失败!${tty_reset}"
  fi

  return "$HAVE_SUDO_ACCESS"
}


abort() {
  printf "%s\n" "$1"
  # exit 1
}

shell_join() {
  local arg
  printf "%s" "$1"
  shift
  for arg in "$@"; do
    printf " "
    printf "%s" "${arg// /\ }"
  done
}

execute() {
  if ! "$@"; then
    abort "$(printf "${tty_red}此命令运行失败: %s${tty_reset}" "$(shell_join "$@")")"
  fi
}



ohai() {
  printf "${tty_blue}运行代码 ==>${tty_bold} %s${tty_reset}\n" "$(shell_join "$@")"
}

# 管理员运行
execute_sudo() 
{

  local -a args=("$@")
  if have_sudo_access; then
    if [[ -n "${SUDO_ASKPASS-}" ]]; then
      args=("-A" "${args[@]}")
    fi
    ohai "/usr/bin/sudo" "${args[@]}"
    execute "/usr/bin/sudo" "${args[@]}"
  else
    ohai "${args[@]}"
    execute "${args[@]}"
  fi
}
#添加文件夹权限
AddPermission()
{
  execute_sudo "/bin/chmod" "-R" "a+rwx" "$1"
  execute_sudo "$CHOWN" "$USER" "$1"
  execute_sudo "$CHGRP" "$GROUP" "$1"
}
#创建文件夹
CreateFolder()
{
    echo '-> 创建文件夹' $1
    execute_sudo "/bin/mkdir" "-p" "$1"
    JudgeSuccess
    AddPermission $1
}

RmAndCopy()
{
  if [[ -d $1 ]]; then
    echo "  ---备份要删除的$1到系统桌面...."
    if ! [[ -d $HOME/Desktop/Old_Homebrew/$TIME/$1 ]]; then
      sudo mkdir -p "$HOME/Desktop/Old_Homebrew/$TIME/$1"
    fi
    sudo cp -rf $1 "$HOME/Desktop/Old_Homebrew/$TIME/$1"
    echo "   ---$1 备份完成"
  fi
  sudo rm -rf $1
}

RmCreate()
{
    RmAndCopy $1
    CreateFolder $1
}

#判断文件夹存在但不可写
exists_but_not_writable() {
  [[ -e "$1" ]] && ! [[ -r "$1" && -w "$1" && -x "$1" ]]
}
#文件所有者
get_owner() {
  $(shell_join "$STAT %u $1" )
}
#文件本人无权限
file_not_owned() {
  [[ "$(get_owner "$1")" != "$(id -u)" ]]
}
#获取所属的组
get_group() {
  $(shell_join "$STAT %g $1" )
}
#不在所属组
file_not_grpowned() {
  [[ " $(id -G "$USER") " != *" $(get_group "$1") "*  ]]
}
#获得当前文件夹权限 例如777
get_permission() {
  $(shell_join "$STAT %A $1" )
}
#授权当前用户权限
user_only_chmod() {
  [[ -d "$1" ]] && [[ "$(get_permission "$1")" != "755" ]]
}


#创建brew需要的目录 直接复制于国外版本，同步
CreateBrewLinkFolder()
{
  echo "--创建Brew所需要的目录"
  directories=(bin etc include lib sbin share opt var
             Frameworks
             etc/bash_completion.d lib/pkgconfig
             share/aclocal share/doc share/info share/locale share/man
             share/man/man1 share/man/man2 share/man/man3 share/man/man4
             share/man/man5 share/man/man6 share/man/man7 share/man/man8
             var/log var/homebrew var/homebrew/linked
             bin/brew)
  group_chmods=()
  for dir in "${directories[@]}"; do
    if exists_but_not_writable "${HOMEBREW_PREFIX}/${dir}"; then
      group_chmods+=("${HOMEBREW_PREFIX}/${dir}")
    fi
  done

  directories=(share/zsh share/zsh/site-functions)
  zsh_dirs=()
  for dir in "${directories[@]}"; do
    zsh_dirs+=("${HOMEBREW_PREFIX}/${dir}")
  done

  directories=(bin etc include lib sbin share var opt
              share/zsh share/zsh/site-functions
              var/homebrew var/homebrew/linked
              Cellar Caskroom Frameworks)
  mkdirs=()
  for dir in "${directories[@]}"; do
    if ! [[ -d "${HOMEBREW_PREFIX}/${dir}" ]]; then
      mkdirs+=("${HOMEBREW_PREFIX}/${dir}")
    fi
  done

  user_chmods=()
  if [[ "${#zsh_dirs[@]}" -gt 0 ]]; then
    for dir in "${zsh_dirs[@]}"; do
      if user_only_chmod "${dir}"; then
        user_chmods+=("${dir}")
      fi
    done
  fi

  chmods=()
  if [[ "${#group_chmods[@]}" -gt 0 ]]; then
    chmods+=("${group_chmods[@]}")
  fi
  if [[ "${#user_chmods[@]}" -gt 0 ]]; then
    chmods+=("${user_chmods[@]}")
  fi

  chowns=()
  chgrps=()
  if [[ "${#chmods[@]}" -gt 0 ]]; then
    for dir in "${chmods[@]}"; do
      if file_not_owned "${dir}"; then
        chowns+=("${dir}")
      fi
      if file_not_grpowned "${dir}"; then
        chgrps+=("${dir}")
      fi
    done
  fi

  if [[ -d "${HOMEBREW_PREFIX}" ]]; then
    if [[ "${#chmods[@]}" -gt 0 ]]; then
      execute_sudo "/bin/chmod" "u+rwx" "${chmods[@]}"
    fi
    if [[ "${#group_chmods[@]}" -gt 0 ]]; then
      execute_sudo "/bin/chmod" "g+rwx" "${group_chmods[@]}"
    fi
    if [[ "${#user_chmods[@]}" -gt 0 ]]; then
      execute_sudo "/bin/chmod" "755" "${user_chmods[@]}"
    fi
    if [[ "${#chowns[@]}" -gt 0 ]]; then
      execute_sudo "$CHOWN" "$USER" "${chowns[@]}"
    fi
    if [[ "${#chgrps[@]}" -gt 0 ]]; then
      execute_sudo "$CHGRP" "$GROUP" "${chgrps[@]}"
    fi
  else
    execute_sudo "/bin/mkdir" "-p" "${HOMEBREW_PREFIX}"
    if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
      execute_sudo "$CHOWN" "root:wheel" "${HOMEBREW_PREFIX}"
    else
      execute_sudo "$CHOWN" "$USER:$GROUP" "${HOMEBREW_PREFIX}"
    fi
  fi

  if [[ "${#mkdirs[@]}" -gt 0 ]]; then
    execute_sudo "/bin/mkdir" "-p" "${mkdirs[@]}"
    execute_sudo "/bin/chmod" "g+rwx" "${mkdirs[@]}"
    execute_sudo "$CHOWN" "$USER" "${mkdirs[@]}"
    execute_sudo "$CHGRP" "$GROUP" "${mkdirs[@]}"
  fi

  if ! [[ -d "${HOMEBREW_REPOSITORY}" ]]; then
    execute_sudo "/bin/mkdir" "-p" "${HOMEBREW_REPOSITORY}"
  fi
  execute_sudo "$CHOWN" "-R" "$USER:$GROUP" "${HOMEBREW_REPOSITORY}"

  if ! [[ -d "${HOMEBREW_CACHE}" ]]; then
    if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
      execute_sudo "/bin/mkdir" "-p" "${HOMEBREW_CACHE}"
    else
      execute "/bin/mkdir" "-p" "${HOMEBREW_CACHE}"
    fi
  fi
  if exists_but_not_writable "${HOMEBREW_CACHE}"; then
    execute_sudo "/bin/chmod" "g+rwx" "${HOMEBREW_CACHE}"
  fi
  if file_not_owned "${HOMEBREW_CACHE}"; then
    execute_sudo "$CHOWN" "-R" "$USER" "${HOMEBREW_CACHE}"
  fi
  if file_not_grpowned "${HOMEBREW_CACHE}"; then
    execute_sudo "$CHGRP" "-R" "$GROUP" "${HOMEBREW_CACHE}"
  fi
  if [[ -d "${HOMEBREW_CACHE}" ]]; then
    execute "$TOUCH" "${HOMEBREW_CACHE}/.cleaned"
  fi
  echo "--依赖目录脚本运行完成"
}

#git提交
git_commit(){
    git add .
    git commit -m "your del"
}

#version_gt 判断$1是否大于$2
version_gt() {
  [[ "${1%.*}" -gt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -gt "${2#*.}" ]]
}
#version_ge 判断$1是否大于等于$2
version_ge() {
  [[ "${1%.*}" -gt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -ge "${2#*.}" ]]
}
#version_lt 判断$1是否小于$2
version_lt() {
  [[ "${1%.*}" -lt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -lt "${2#*.}" ]]
}

#发现错误 关闭脚本 提示如何解决
error_game_over(){
    echo "
    ${tty_red}失败$MY_DOWN_NUM 右键下面地址查看常见错误解决办法
    https://github.com/TheRamU/Fay
    如果没有解决，把全部运行过程截图发到 467665317@qq.com ${tty_reset}
    "

    exit 0
}

#一些警告判断
warning_if(){
  git_https_proxy=$(git config --global https.proxy)
  git_http_proxy=$(git config --global http.proxy)
  if [[ -z "$git_https_proxy"  &&  -z "$git_http_proxy" ]]; then
  echo "未发现Git代理（属于正常状态）"
  else
  echo "${tty_yellow}
      提示：发现你电脑设置了Git代理，如果Git报错，请运行下面两句话：

              git config --global --unset https.proxy

              git config --global --unset http.proxy${tty_reset}
  "
  fi
}

echo "
              ${tty_green} 开始执行Brew自动安装程序 ${tty_reset}
             ${tty_cyan} [467665317@qq.com] ${tty_reset}
           ['$TIME']['$macos_version']
       ${tty_cyan} https://github.com/TheRamU/Fay${tty_reset}
"
#选择一个brew下载源
echo -n "${tty_green}
请选择一个下载brew本体的序号，例如中科大，输入1回车。
源有时候不稳定，如果git克隆报错重新运行脚本选择源。
1、中科大下载源
2、清华大学下载源
3、北京外国语大学下载源 ${tty_reset}"
if [[ $GIT_SPEED == "" ]]; then
  echo -n "${tty_green}
4、腾讯下载源 
5、阿里巴巴下载源 ${tty_reset}"
fi
echo -n "
${tty_blue}请输入序号: "
read MY_DOWN_NUM
echo "${tty_reset}"
case $MY_DOWN_NUM in
"2")
    echo "
    你选择了清华大学brew本体下载源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/
    #HomeBrew基础框架
    USER_BREW_GIT=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git
    #HomeBrew Core
    USER_CORE_GIT=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git
    #HomeBrew Cask
    USER_CASK_GIT=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-cask.git
    USER_CASK_FONTS_GIT=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-cask-fonts.git
    USER_CASK_DRIVERS_GIT=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-cask-drivers.git
;;
"3")
    echo "
    北京外国语大学brew本体下载源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.bfsu.edu.cn/homebrew-bottles
    #HomeBrew基础框架
    USER_BREW_GIT=https://mirrors.bfsu.edu.cn/git/homebrew/brew.git
    #HomeBrew Core
    USER_CORE_GIT=https://mirrors.bfsu.edu.cn/git/homebrew/homebrew-core.git
    #HomeBrew Cask
    USER_CASK_GIT=https://mirrors.bfsu.edu.cn/git/homebrew/homebrew-cask.git
    USER_CASK_FONTS_GIT=https://mirrors.bfsu.edu.cn/git/homebrew/homebrew-cask-fonts.git
    USER_CASK_DRIVERS_GIT=https://mirrors.bfsu.edu.cn/git/homebrew/homebrew-cask-drivers.git
;;
"4")
    echo "
    你选择了腾讯brew本体下载源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.cloud.tencent.com/homebrew-bottles
    #HomeBrew基础框架
    USER_BREW_GIT=https://mirrors.cloud.tencent.com/homebrew/brew.git 
    #HomeBrew Core
    USER_CORE_GIT=https://mirrors.cloud.tencent.com/homebrew/homebrew-core.git
    #HomeBrew Cask
    USER_CASK_GIT=https://mirrors.cloud.tencent.com/homebrew/homebrew-cask.git
;;
"5")
    echo "
    你选择了阿里巴巴brew本体下载源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.aliyun.com/homebrew/homebrew-bottles
    #HomeBrew基础框架
    USER_BREW_GIT=https://mirrors.aliyun.com/homebrew/brew.git 
    #HomeBrew Core
    USER_CORE_GIT=https://mirrors.aliyun.com/homebrew/homebrew-core.git
    #HomeBrew Cask
    USER_CASK_GIT=https://mirrors.aliyun.com/homebrew/homebrew-cask.git
;;
*)
  echo "
  你选择了中国科学技术大学brew本体下载源
  "
  #HomeBrew 下载源 install
  USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles
  #HomeBrew基础框架
  USER_BREW_GIT=https://mirrors.ustc.edu.cn/brew.git
  #HomeBrew Core
  USER_CORE_GIT=https://mirrors.ustc.edu.cn/homebrew-core.git
  #HomeBrew Cask
  USER_CASK_GIT=https://mirrors.ustc.edu.cn/homebrew-cask.git
;;
esac
echo -n "${tty_green}！！！此脚本将要删除之前的brew(包括它下载的软件)，请自行备份。
->是否现在开始执行脚本（N/Y） "
read MY_Del_Old
echo "${tty_reset}"
case $MY_Del_Old in
"y")
echo "--> 脚本开始执行"
;;
"Y")
echo "--> 脚本开始执行"
;;
*)
echo "你输入了 $MY_Del_Old ，自行备份老版brew和它下载的软件, 如果继续运行脚本应该输入Y或者y
"
exit 0
;;
esac


if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
#MAC
  echo "${tty_yellow} Mac os设置开机密码方法：
  (设置开机密码：在左上角苹果图标->系统偏好设置->"用户与群组"->更改密码)
  (如果提示This incident will be reported. 在"用户与群组"中查看是否管理员) ${tty_reset}"
fi

echo "==> 通过命令删除之前的brew、创建一个新的Homebrew文件夹
${tty_cyan}请输入开机密码，输入过程不显示，输入完后回车${tty_reset}"

sudo echo '开始执行'
#删除以前的Homebrew
RmCreate ${HOMEBREW_REPOSITORY}
RmAndCopy $HOMEBREW_CACHE
RmAndCopy $HOMEBREW_LOGS

# 让环境暂时纯粹，脚本运行结束后恢复
if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
    export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOMEBREW_REPOSITORY}/bin
fi
git --version
if [ $? -ne 0 ];then

    if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
        sudo rm -rf "/Library/Developer/CommandLineTools/"
        echo "${tty_cyan}安装Git${tty_reset}后再运行此脚本，${tty_red}在系统弹窗中点击“安装”按钮
        如果没有弹窗的老系统，需要自己下载安装：https://sourceforge.net/projects/git-osx-installer/ ${tty_reset}"
        xcode-select --install
        exit 0
    else
        echo "${tty_red} 发现缺少git，开始安装，请输入Y ${tty_reset}"
        sudo apt install git
    fi
fi

echo "
${tty_cyan}下载速度觉得慢可以ctrl+c或control+c重新运行脚本选择下载源${tty_reset}
==> 从 $USER_BREW_GIT 克隆Homebrew基本文件
"
warning_if
sudo git clone ${GIT_SPEED} $USER_BREW_GIT ${HOMEBREW_REPOSITORY}
JudgeSuccess 尝试再次运行自动脚本选择其他下载源或者切换网络 out

#依赖目录创建 授权等等
CreateBrewLinkFolder

echo '==> 创建brew的替身'
if [[ "${HOMEBREW_REPOSITORY}" != "${HOMEBREW_PREFIX}" ]]; then
  find ${HOMEBREW_PREFIX}/bin -name brew -exec sudo rm -f {} \;
  execute "ln" "-sf" "${HOMEBREW_REPOSITORY}/bin/brew" "${HOMEBREW_PREFIX}/bin/brew"
fi

echo "==> 从 $USER_CORE_GIT 克隆Homebrew Core
${tty_cyan}此处如果显示Password表示需要再次输入开机密码，输入完后回车${tty_reset}"
sudo mkdir -p ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-core
sudo git clone ${GIT_SPEED} $USER_CORE_GIT ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-core/
JudgeSuccess 尝试再次运行自动脚本选择其他下载源或者切换网络 out

if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
#MAC
  echo "==> 从 $USER_CASK_GIT 克隆Homebrew Cask 图形化软件
  ${tty_cyan}此处如果显示Password表示需要再次输入开机密码，输入完后回车${tty_reset}"
  sudo mkdir -p ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-cask
  sudo git clone ${GIT_SPEED} $USER_CASK_GIT ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-cask/
  if [ $? -ne 0 ];then
      sudo rm -rf ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-cask
      echo "${tty_red}尝试切换下载源或者切换网络,不过Cask组件非必须模块。可以忽略${tty_reset}"
  else
      echo "${tty_green}此步骤成功${tty_reset}"

  fi

  echo "==> 从 $USER_SERVICES_GIT 克隆Homebrew services 管理服务的启停
  "
  sudo mkdir -p ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-cask
  sudo git clone ${GIT_SPEED} $USER_SERVICES_GIT ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-services/
  JudgeSuccess
else
#Linux
  echo "${tty_yellow} Linux 不支持Cask图形化软件下载 此步骤跳过${tty_reset}"
fi
echo '==> 配置国内镜像源HOMEBREW BOTTLE'

#判断下mac os终端是Bash还是zsh
case "$SHELL" in
  */bash*)
    if [[ -r "$HOME/.bash_profile" ]]; then
      shell_profile="${HOME}/.bash_profile"
    else
      shell_profile="${HOME}/.profile"
    fi
    ;;
  */zsh*)
    shell_profile="${HOME}/.zprofile"
    ;;
  *)
    shell_profile="${HOME}/.profile"
    ;;
esac

if [[ -n "${HOMEBREW_ON_LINUX-}" ]]; then
  #Linux
  shell_profile="/etc/profile"
fi

if [[ -f ${shell_profile} ]]; then
  AddPermission ${shell_profile}
fi
#删除之前的环境变量
if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
  #Mac
  sed -i "" "/ckbrew/d" ${shell_profile}
else
  #Linux
  sed -i "/ckbrew/d" ${shell_profile}
fi

#选择一个homebrew-bottles下载源
echo -n "${tty_green}

            Brew本体已经安装成功，接下来配置国内源。

请选择今后brew install的时候访问那个国内镜像，例如阿里巴巴，输入5回车。

1、中科大国内源
2、清华大学国内源
3、北京外国语大学国内源
4、腾讯国内源 
5、阿里巴巴国内源 ${tty_reset}"

echo -n "
${tty_blue}请输入序号: "
read MY_DOWN_NUM
echo "${tty_reset}"
case $MY_DOWN_NUM in
"2")
    echo "
    你选择了清华大学国内源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/
;;
"3")
    echo "
    北京外国语大学国内源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.bfsu.edu.cn/homebrew-bottles
;;
"4")
    echo "
    你选择了腾讯国内源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.cloud.tencent.com/homebrew-bottles
;;
"5")
    echo "
    你选择了阿里巴巴国内源
    "
    USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.aliyun.com/homebrew/homebrew-bottles
;;
*)
  echo "
  你选择了中国科学技术大学国内源
  "
  #HomeBrew 下载源 install
  USER_HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles
;;
esac

#写入环境变量到文件
echo "

        环境变量写入->${shell_profile}

"

echo "
  export HOMEBREW_BOTTLE_DOMAIN=${USER_HOMEBREW_BOTTLE_DOMAIN} #ckbrew
  eval \$(${HOMEBREW_REPOSITORY}/bin/brew shellenv) #ckbrew
" >> ${shell_profile} 
JudgeSuccess
source "${shell_profile}"
if [ $? -ne 0 ];then
    echo "${tty_red}发现错误，${shell_profile} 文件中有错误，建议根据上一句提示修改；
                否则会导致提示 permission denied: brew${tty_reset}"
fi

AddPermission ${HOMEBREW_REPOSITORY}

if [[ -n "${HOMEBREW_ON_LINUX-}" ]]; then
    #检测linux curl是否有安装
    echo "${tty_red}-检测curl是否安装 留意是否需要输入Y${tty_reset}"
    curl -V
    if [ $? -ne 0 ];then
        sudo apt-get install curl
        if [ $? -ne 0 ];then
            sudo yum install curl
            if [ $? -ne 0 ];then
                echo '失败 请自行安装curl 可以参考https://www.howtoing.com/install-curl-in-linux'
                error_game_over
            fi
        fi
    fi
fi

echo '
==> 安装完成，brew版本
'
brew -v
if [ $? -ne 0 ];then
    echo '发现错误，自动修复一次！'
    rm -rf $HOMEBREW_CACHE
    export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOMEBREW_REPOSITORY}/bin
    brew update-reset
    brew -v
    if [ $? -ne 0 ];then
      error_game_over
    fi
else
    echo "${tty_green}Brew前期配置成功${tty_reset}"
fi

#brew 3.1.2版本 修改了很多地址，都写死在了代码中，没有调用环境变量。。额。。
#ruby下载需要改官方文件
ruby_URL_file=$HOMEBREW_REPOSITORY/Library/Homebrew/cmd/vendor-install.sh

#判断Mac系统版本
if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
  if version_gt "$macos_version" "10.14"; then
      echo "电脑系统版本：$macos_version"
  else
      echo "${tty_red}检测到你不是最新系统，会有一些报错，请稍等Ruby下载安装;${tty_reset}
      "
  fi

  if [[ -f ${ruby_URL_file} ]]; then
      sed -i "" "s/ruby_URL=/ruby_URL=\"https:\/\/mirrors.tuna.tsinghua.edu.cn\/homebrew-bottles\/bottles-portable-ruby\/\$ruby_FILENAME\" \#/g" $ruby_URL_file
  fi
else
  if [[ -f ${ruby_URL_file} ]]; then
      sed -i "s/ruby_URL=/ruby_URL=\"https:\/\/mirrors.tuna.tsinghua.edu.cn\/linuxbrew-bottles\/bottles-portable-ruby\/\$ruby_FILENAME\" \#/g" $ruby_URL_file
  fi
fi

brew services cleanup

if [[ $GIT_SPEED == "" ]];then
  echo '
  ==> brew update-reset
  '
  brew update-reset
  if [[ $? -ne 0 ]];then
      brew config
      error_game_over
      exit 0
  fi
else
   #极速模式提示Update修复方法
    echo "
${tty_red}  极速版本安装完成，${tty_reset} install功能正常，如果需要update功能请自行运行下面三句命令
git -C ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-core fetch --unshallow
git -C ${HOMEBREW_REPOSITORY}/Library/Taps/homebrew/homebrew-cask fetch --unshallow
brew update-reset
  "
fi

echo "
        ${tty_green}Brew自动安装程序运行完成${tty_reset}
          ${tty_green}国内地址已经配置完成${tty_reset}

  桌面的Old_Homebrew文件夹，大致看看没有你需要的可以删除。

              初步介绍几个brew命令
本地软件库列表：brew ls
查找软件：brew search google（其中google替换为要查找的关键字）
查看brew版本：brew -v  更新brew版本：brew update
安装cask软件：brew install --cask firefox 把firefox换成你要安装的
        ${tty_green}
        欢迎右键点击下方地址-打开URL 来给个星${tty_reset}
        ${tty_underline} https://github.com/TheRamU/Fay ${tty_reset}
"

if [[ -z "${HOMEBREW_ON_LINUX-}" ]]; then
  #Mac
  echo "${tty_red} 安装成功 但还需要重启终端 或者 运行${tty_bold} source ${shell_profile}  ${tty_reset} ${tty_red}否则可能无法使用${tty_reset}
  "
else
  #Linux
  echo "${tty_red} Linux需要重启电脑 或者暂时运行${tty_bold} source ${shell_profile} ${tty_reset} ${tty_red}否则可能无法使用${tty_reset}
  "
fi
