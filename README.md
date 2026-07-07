Simple Serial Logger, that takes raw, structured data, and dumps it into a .csv. It is designed
for restricted Serial port Usage (think 115200 baud, so every byte counts). 
It will pick up on any serial port, and begin reading.
On Exit (Control + C), it will proceed to output the read data as a .csv. 

For example:
python3 logger.py -si sample.json -fo out.csv -sp COM1 -br 921600
will log the 4,4,4 packets with a single newline char (so 13 bytes total) with the date/time into the csv

running head on the output will output something along the lines of:
2026-07-07 11:46:34.091968,XXXX,XXXX,XXXX
where the Xs are the data received in this scenario. 
