amzmg: Amazon MP3 Getter for Linux
==================================
 This python script monitors an Amazon account for new music purchases and automatically downloads them to a specified location. 
 It is unique from other Linux downloaders in that it works directly with your amazon account, instead of being fed .amz files.

 On first run, the script will ask a few setup questions like your amazon account and where to download the music to.

 Amzmg was developed to automatically pull in new purchases onto local disk. It has no GUI and is best used by leaving it alone as a persistent background daemon.
 This way, your music will show up at the path you configured, whether you purchased it on your smartphone away from home or from a browser on the same PC amzmg runs on. Amzmg will recheck your account every two minutes by default, and immediate checks can be triggered by sending it a SIGUSR1.
 Given the limited downloader options for Linux users, it's not too bad if you prefer to run it in the foreground manually after making a purchase, too.
 
 Amzmg is, of course, dependent on particular web services Amazon operates. This code is compatible as of 11/15/2014 (and long before; the interface seems fairly stable.)
 
Usage
-----
 * In the foreground: ./amzmg.py
 * As a daemon: ./amzmg.py --daemonize
 * Update configuration: ./amzmg.py -u

 Additional usage documentation via /.amzmg.py -h
 
TODO
----
 * Make friendly setup scripts / packages for different platforms
 * Flesh out actual music download code to handle download anomalies, name files per user-defined format, etc
 * Make loglevel a configuration setting
 