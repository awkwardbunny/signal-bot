#FROM python:3-bullseye
#FROM openjdk:slim
#COPY --from=python:3-bullseye / /
FROM brian/java-python

# Install signal-cli
ARG SIGNAL_CLI_VERSION=0.8.5
RUN wget https://github.com/AsamK/signal-cli/releases/download/v"${SIGNAL_CLI_VERSION}"/signal-cli-"${SIGNAL_CLI_VERSION}".tar.gz
RUN tar xf signal-cli-"${SIGNAL_CLI_VERSION}".tar.gz -C /opt
RUN rm signal-cli-"${SIGNAL_CLI_VERSION}".tar.gz
RUN ln -sf /opt/signal-cli-"${SIGNAL_CLI_VERSION}"/bin/signal-cli /usr/local/bin/
RUN ln -sf /opt/signal-cli-"${SIGNAL_CLI_VERSION}" /opt/signal-cli

# Install dbus and config file
RUN apt-get update && apt-get install -y dbus libdbus-1-dev libgirepository1.0-dev fortune cowsay iputils-ping figlet sysvbanner
COPY ./org.asamk.Signal.conf /etc/dbus-1/system.d/
COPY ./org.asamk.Signal.service /usr/share/dbus-1/system-services/

RUN mkdir /signal-data

# Switch to signal user
RUN useradd -m signal
USER signal
WORKDIR /home/signal

# Install python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot.py .
COPY run.sh .

USER root

RUN chmod 0744 run.sh requirements.txt bot.py

ENV PATH="/usr/games:${PATH}"
ENV DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"
ENV TZ="America/New_York"
CMD bash
ENTRYPOINT ["/home/signal/run.sh"]
CMD ["+1"]

