Simple Serial Logger, that takes raw, structured data, and dumps it into a .csv. It is designed
for restricted Serial port Usage (think 115200 baud, so every byte counts). 
It will pick up on any serial port, and begin reading.
On Exit (Control + C), it will proceed to output the read data as a .csv. 
