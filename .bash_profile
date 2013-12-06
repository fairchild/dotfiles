# Add `~/bin` to the `$PATH`
export PATH="$HOME/bin:$PATH"

# Load the shell dotfiles, and then some:
# * ~/.path can be used to extend `$PATH`.
# * ~/.extra can be used for other settings you don’t want to commit.
for file in ~/.{path,bash_prompt,exports,aliases,functions,extra}; do
	[ -r "$file" ] && source "$file"
done
unset file

# Case-insensitive globbing (used in pathname expansion)
shopt -s nocaseglob

# Append to the Bash history file, rather than overwriting it
shopt -s histappend

# Autocorrect typos in path names when using `cd`
shopt -s cdspell

# Enable some Bash 4 features when possible:
# * `autocd`, e.g. `**/qux` will enter `./foo/bar/baz/qux`
# * Recursive globbing, e.g. `echo **/*.txt`
for option in autocd globstar; do
	shopt -s "$option" 2> /dev/null
done

# Prefer US English and use UTF-8
export LC_ALL="en_US.UTF-8"
export LANG="en_US"

# Add tab completion for SSH hostnames based on ~/.ssh/config, ignoring wildcards
[ -e "$HOME/.ssh/config" ] && complete -o "default" -o "nospace" -W "$(grep "^Host" ~/.ssh/config | grep -v "[?*]" | cut -d " " -f2)" scp sftp ssh

# Add tab completion for `defaults read|write NSGlobalDomain`
# You could just use `-g` instead, but I like being explicit
if [[ `uname`=='Darwin' ]]; then
  echo 'Darwin'
	complete -W "NSGlobalDomain" defaults
	# Add `killall` tab completion for common apps
	complete -o "nospace" -W "Contacts Calendar Dock Finder Mail Safari iTunes SystemUIServer Terminal Twitter" killall

	# set sublime as the default editor
	export EDITOR='subl -w'
else
  echo "`uname` detected, with no extra settings."
  export EDITOR='vim'
fi


# If possible, add tab completion for many more commands
[ -f /etc/bash_completion ] && source /etc/bash_completion


bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

if [[ -f $HOME/.nvm/nvm.sh ]]; then
  source $HOME/.nvm/nvm.sh
fi


if [ -f /usr/local/etc/bash_completion ]; then
  source /usr/local/etc/bash_completion
fi
if [ -f $HOME/.bash_completion/docker.bash ]; then
  source $HOME/.bash_completion/docker.bash
fi


if [[ -f  $HOME/.rvm/scripts/rvm ]]; then
  source $HOME/.rvm/scripts/rvm
fi


# =========================================================
# AWS config
# =========================================================

if [ -f "$HOME/Dropbox/cloudteam/ec2_api_tools/environment" ]; then
	. $HOME/Dropbox/cloudteam/ec2_api_tools/ec2-switch-context
fi

if [ -z "$EC2_CONFIG_DIR" ]; then
   if [ -d ~/.ec2/current ]; then
    echo "setting EC2_CONFIG_DIR to default ~/.ec2/current"
   	export EC2_CONFIG_DIR=~/.ec2/current
  fi
fi

if [[ ! -z "$EC2_CONFIG_DIR" ]]; then
	if [[ -f $EC2_CONFIG_DIR/environment ]]; then
	  . $EC2_CONFIG_DIR/environment
	fi
	if [[ -f $EC2_CONFIG_DIR/novarc ]]; then
	  echo "sourcing $EC2_CONFIG_DIR/novarc"
     . $EC2_CONFIG_DIR/novarc
   elif [[ -f "$EC2_CONFIG_DIR/*-openrc.sh"  ]]; then
     echo "sourcing $EC2_CONFIG_DIR/*-openrc.sh "
     . $EC2_CONFIG_DIR/*openrc.sh
   else
     echo "no novarc found in $EC2_CONFIG_DIR" 
	fi
fi


dotfiles_prompt