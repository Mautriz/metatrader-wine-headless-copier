# Start from the pywine image (contains Wine + Windows Python)
FROM tobix/pywine:3.12

# Set the Wine environment
ENV WINEARCH=win64
# Disable the pop-up installers for Mono and Gecko
ENV WINEDLLOVERRIDES="mscoree,mshtml="


WORKDIR /app

# 1. Install unzip to handle your meta.zip
USER root
# RUN apt-get update && apt-get install -y unzip xvfb && rm -rf /var/lib/apt/lists/*

# 2. Extract your MT5 installation into Wine's drive_c
# Path in container: /root/.wine/drive_c/mt5
COPY meta.zip .
# mkdir -p '/opt/wineprefix/drive_c/Program Files' && \
RUN  unzip meta.zip -d '/opt/wineprefix/drive_c/Program Files' && \
    rm meta.zip

RUN apt-get update && \
    apt-get install -y wget cabextract xvfb && \
    wget -q -O /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks && \
    chmod +x /usr/local/bin/winetricks && \
    rm -rf /var/lib/apt/lists/*

RUN wineboot --init && \
    wineserver -w && \
    xvfb-run winetricks -q win10 && \
    wineserver -w && \
    xvfb-run winetricks -q vcrun2019 && \
    wineserver -w

COPY requirements.txt .
RUN wine python -m pip install --no-cache-dir -r requirements.txt

# 5. Force Native DLLs
# Now we strictly enforce the native ucrtbase we just installed.
ENV WINEDLLOVERRIDES="mscoree,mshtml=;ucrtbase=n,b"



COPY ./volumes/ /volumes/
RUN rm -f "/opt/wineprefix/drive_c/Program Files/meta/Config/servers.dat" && \
    cp /volumes/servers.dat "/opt/wineprefix/drive_c/Program Files/meta/Config/servers.dat" && \
    rm -f "/opt/wineprefix/drive_c/Program Files/meta/Config/common.ini" && \
    cp /volumes/common.ini "/opt/wineprefix/drive_c/Program Files/meta/Config/common.ini"

# 4. Copy your trading script
COPY script.py .

# 5. Run the script
# xvfb-run is required because MT5 is a GUI app and needs a virtual display
# CMD ["sleep", "infinity"]
CMD ["xvfb-run", "-a", "-s", "-screen 0 1x1x8", "wine", "python", "script.py"]