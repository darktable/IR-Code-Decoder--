#! /usr/bin/python
# ---------------------------------------------------------------------#
# Name - IR&NECDataCollect.py (renamed remotereader.py)
# Description - Reads data from the IR sensor but uses the official NEC Protocol (command line version)
# Author - Lime Parallelogram
# Licence - Attribution Lime
# Date - 06/07/19 - 18/08/19
# ---------------------------------------------------------------------#
# Imports modules
import sys
import argparse
import os
import json
from time import clock

import RPi.GPIO as GPIO

PULSE_MICROSECS = 1000
SPACE_MICROSECS = 2000
SECONDS_TO_MICROSECS = 1000000
COMMAND_END_SECS = 0.25


class FatalError(Exception):
    def __init__(self, msg):
        self.msg = msg


def get_data(pin_in=11):  # Pulls data from sensor
    command = []  # Pulses and their timings
    previous_value = 0  # The previous pin state
    value = -1

    while value != 0:  # Waits until pin is pulled low
        value = GPIO.input(pin_in)

    last_pulse = clock()

    while True:
        if value != previous_value:  # Waits until change in state occurs
            pulse_duration = int((clock() - last_pulse) * SECONDS_TO_MICROSECS)  # Calculate time in between pulses

            # Adds pulse time to array (previous val acts as an alternating 1 / 0
            # to show whether time is the on time or off time)
            command.append((previous_value, pulse_duration))
            previous_value = value

            last_pulse = clock()

        # if no value change for a while the command is over
        if clock() - last_pulse > COMMAND_END_SECS:
            break

        # Reads values again
        value = GPIO.input(pin_in)

    return parse_command(command)


def parse_command(command):
    # print(json.dumps(command))

    # Convert data to binary string
    output = []
    binary = []
    command_started = False

    for (typ, tme) in command:
        # there's always a long high and long low at the start of a command
        if typ == 0 and tme < PULSE_MICROSECS:
            command_started = True

        if command_started and typ == 1:
            # gap over 1800 seems to indicate the space between commands
            # (e.g. long press of button of multi-chunk air conditioner command)
            if tme > SPACE_MICROSECS:
                output.append(''.join(binary))
                binary = []
                continue

            # According to NEC protocol a gap of 1687.5 microseconds represents
            # a logical 1 so over 1000 should make a big enough distinction
            if tme > PULSE_MICROSECS:
                binary.append('1')
            else:
                binary.append('0')

    output.append(''.join(binary))

    return output


def convert_oct(binary_value):  # Converts binary string to hexadecimal
    tmp_b2 = int(binary_value, 2)
    return str(oct(tmp_b2))


def convert_hex(binary_value):  # Converts binary string to hexadecimal
    tmp_b2 = int(binary_value, 2)
    return str(hex(tmp_b2))


def check_positive(value):
    int_value = int(value)
    if int_value <= 0:
        raise argparse.ArgumentTypeError('count must be larger than zero')
    return int_value


def load_json_file(path):
    with open(path, 'r') as infile:
        data = json.load(infile)
    return data


def save_json_file(out_path, data):
    with open(out_path, 'w') as outfile:
        json.dump(data, outfile, indent=2, sort_keys=True)


def main(argv):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(description='Read codes from IR remotes')
    parser.add_argument('--pin', '-p', type=check_positive, default=11, help='GPIO pin to read from')
    parser.add_argument('output', help='where codes will be written')

    args = parser.parse_args(argv[1:])

    start_time = clock()

    remote_data = {}
    out_path = os.path.abspath(args.output)

    try:
        # if output file exists read json from it
        if os.path.exists(out_path):
            remote_data = load_json_file(out_path)

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(args.pin, GPIO.IN)

        while True:
            bin_array = get_data(args.pin)

            deduped = []
            last_bin = None
            for bin_value in bin_array:
                # message less than a byte are assumed to be noise
                if bin_value is None or len(bin_value) < 8:
                    continue

                # remove repeated values (button held for long period)
                if bin_value != last_bin:
                    last_bin = bin_value
                    deduped.append(bin_value)

            if len(deduped) == 0:
                continue

            merged_bin = " ".join(deduped)

            if merged_bin not in remote_data:
                print("bits: {0} bin: {1}".format(len(merged_bin), merged_bin))

                name = raw_input("name this command: ").strip()

                remote_data[str(merged_bin)] = name
            else:
                command = remote_data[merged_bin]
                print("command: {0}\nbin: {1}".format(command, merged_bin))

    except (KeyboardInterrupt, SystemExit) as e:
        print("\nbye.")
        return 1
    except FatalError as err:
        print(err.msg)
        return 1
    finally:
        GPIO.cleanup()

        if len(remote_data) > 0:
            save_json_file(out_path, remote_data)

        print("\nduration: {0} seconds".format(clock() - start_time))


if __name__ == "__main__":
    main(sys.argv)
