# OGN Privacy Filter

A script to selectively forward APRS packets.

The script listens for incoming connections by ogn-decode
and connects to an APRS-Server (aprs-pool.glidernet.org).
Every hour it fetches the DDB to update the local whitelist.

Received packets from the station are only forwared if the
NoTrack-Flag in the DDB is _not_ set ('Opt-In') or if they
are from the station itself.
All the packets from the APRS-Server are forwarded to the station.


## Installation

1. Get the dependencies via pip or manual installion.

   ```
   sudo apt-get intall python3-pip
   sudo pip3 install aprslib requests
   ```
   or
   ```
   $ sudo apt-get install python3-setuptools python3-requests
   $ wget https://pypi.python.org/packages/source/a/aprslib/aprslib-0.6.40.tar.gz
   $ tar xzf aprslib-0.6.40.tar.gz
   $ cd aprslib-0.6.40/
   $ sudo pyton3 setup.py install
   ```

2. Clone Repository

   ```
   $ git clone https://github.com/kerel-fs/ogn-privacy-filter.git /opt/ogn-privacy-filter
   ```


3. Configure ogn-decode / manipulate DNS cache

   ~~Currently (v0.2.3) you can't configure the address
   ogn-decode connects to (`aprs.glidernet.org` is hardcoded),
   so you have to manipulate your local DNS cache.~~

   Set the address ogn-decode connects to in the receiver configuration file.
   ```
   $ sudo vi /etc/rtlsdr-ogn/site.conf

   APRS:
   { Call = "N0CALL";
     Server = "127.0.2.1:14580";
   } ;
   ```


4. Install as service

   To install it as a service, edit your shellbox configuration file:
   ```
   $ sudo vi /etc/rtlsdr-ogn.conf

   #shellbox configuration file
   #port  user    directory           command      args
   50002  ogn /opt/ogn-privacy-filter ./privacyFilter.py
   50000  ogn /opt/rtlsdr-ogn         ./ogn-rf     /etc/rtlsdr-ogn/site.conf
   50001  ogn /opt/rtlsdr-ogn         ./ogn-decode /etc/rtlsdr-ogn/site.conf
   ```

And finally:
```
$ sudo service rtlsdr-ogn start
```

## Development

For testing purposes, you can run it from the command line:
```
$ cd ogn-privacy-filter
$ ./privacyFilter.py
Listen for new client at 127.0.2.1:14580
Connected to server 37.187.40.234:14580
[...]
```

To get debug messages, create a short startup script:
```
#!/usr/bin/env python3

import logging
from privacyFilter import privacyFilter


if __name__ == "__main__":
    FORMAT = '%(asctime)-15s %(levelname)-5s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    client_adress = ('127.0.2.1', 14580)
    server_address = ('aprs-pool.glidernet.org', 14580)
    ddbInterval = 3600

    f = privacyFilter(clients_address, server_address, ddbInterval)
    f.logger.setLevel(logging.DEBUG)
    f.run()
```


## TODO

Some minor improvements are necessary / should be considered.
- Clear `*_queues` if connection get closed?
- Check output of `socket.send()` for remaining data?
- Missing prefix generation in `ognutils.py`

## License

Licensed under the [GPLv3](LICENSE).
