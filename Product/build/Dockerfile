FROM ubuntu:22.04

RUN apt update \
    && apt upgrade -y \
    && apt-get install -y software-properties-common git pkg-config mysql-client libmysqlclient-dev default-libmysqlclient-dev build-essential

RUN apt install sudo

# Create ubuntu user
RUN useradd -rm -d /home/ubuntu -p "$(openssl passwd -1 ubuntu)" -s /bin/bash -g root -G sudo -u 1001 ubuntu \
    && usermod -aG sudo ubuntu

RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> \
    /etc/sudoers

SHELL ["/bin/bash", "--login", "-i", "-c"]

# Make the local bin directory writeable by the ubuntu user
RUN chown -R ubuntu /usr/local/bin /home/ubuntu/

# Change to non-root user to install everything else
USER ubuntu
WORKDIR /home/ubuntu/workspace

# Install pyenv
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv
ENV PYENV_ROOT=/home/ubuntu/.pyenv
ENV PATH=/home/ubuntu/.pyenv/bin:/home/ubuntu/.pyenv/shims:$PATH

RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
RUN echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.bashrc
RUN sudo apt install -y gcc zlib1g-dev bzip2 libbz2-dev libreadline-dev sqlite libsqlite3-dev libssl-dev libffi-dev vim tar curl wget make python3-dev supervisor

# pyenv is on PATH via ENV above, so this uses the login SHELL and does not need bash -xc
RUN pyenv install 3.13 && pyenv global 3.13

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
ENV PATH="/home/ubuntu/.local/bin:${PATH}"
RUN poetry --version

RUN echo 'export PATH="/home/ubuntu/workspace/src/.venv/bin:$PATH"' >> ~/.bashrc

COPY . .
COPY ./build/supervisor.conf .
COPY ./build/run.sh .
COPY ./build/start-job-runner.sh .
RUN sudo chmod +x ./run.sh ./build/run.sh ./start-job-runner.sh ./build/start-job-runner.sh
RUN sudo rm -rf ./temp_download_files ./temp_upload_files ./client
RUN rm -f ./powerchoice.env
RUN rm -f ./.env
RUN mkdir -p ./static ./static_client ./temp_download_files ./temp_upload_files ../tmp ../tmp/logs ./tmp/logs /home/ubuntu/tmp/logs
RUN sudo rm -rf ./src/.venv
RUN sudo chown -R $(whoami) ../*
RUN cd /home/ubuntu/workspace/src && poetry install

CMD ["./run.sh"]