"""
Useful functions for plotting and playing pianorolls for Comper
"""
import subprocess
import pypianoroll
from matplotlib import pyplot as plt
import numpy as np
import mido
from mido import Message, MidiFile, MidiTrack
# Dataset definitions
# NUM_PITCHES = 128
# PARTITION_NOTE = 60 # Break into left- and right-accompaniments at middle C
# BEAT_RESOLUTION = 24 # This is set by the encoding of the lpd-5 dataset, corresponds to number of ticks per beat
# BEATS_PER_UNIT = 4
# TICKS_PER_UNIT = BEATS_PER_UNIT * BEAT_RESOLUTION

def crop_pianoroll(pianoroll, min_pitch, max_pitch):
    """
    Given a pianoroll of shape(NUM_TICKS, 128),
    crop the pitch axis to range from min_pitch:max_pitch+1
    (inclusive of min_pitch and max_pitch)
    """
    assert pianoroll.shape[1] == 128
    output = pianoroll[:, min_pitch:max_pitch+1] # Crop pitch range of pianoroll
    assert output.shape[1] == max_pitch - min_pitch + 1
    return output

def pad_pianoroll(pianoroll, min_pitch, max_pitch):
    """
    Given a pianoroll of shape (NUM_TICKS, NUM_PITCHES),
    return a zero-padded matrix (NUM_TICKS, 128)
    """
    assert pianoroll.shape[1] == max_pitch - min_pitch + 1
    ticks = pianoroll.shape[0]
    front = np.zeros((ticks, min_pitch-1))
    back = np.zeros((ticks, 128-max_pitch))
    output = np.hstack((front, pianoroll, back))
    assert output.shape[1] == 128
    return output

def plot_pianoroll(ax, pianoroll, min_pitch=0, max_pitch=127, beat_resolution=None, cmap='Blues'):
    """
    Plots a pianoroll matrix, code adapted from 
    https://salu133445.github.io/pypianoroll/_modules/pypianoroll/plot.html#plot_pianoroll
    """
    assert pianoroll.shape[1] == max_pitch - min_pitch + 1
    ax.imshow(pianoroll.T, cmap=cmap, aspect='auto', 
              vmin=0, vmax=1, origin='lower', interpolation='none')
    ax.set_ylabel('pitch')
    lowest_octave = ((min_pitch - 1) // 12 + 1) - 2
    highest_octave = max_pitch // 12 - 2
    ax.set_yticks(np.arange((lowest_octave + 2) * 12, max_pitch+1, 12) - min_pitch)
    ax.set_yticklabels(['C{}'.format(i) for i in range(lowest_octave, highest_octave + 1)])
    
    ax.set_xlabel('ticks')
    # Beat lines
    if beat_resolution is not None:
        num_beat = pianoroll.shape[0]//beat_resolution
        xticks_major = beat_resolution * np.arange(0, num_beat)
        xticks_minor = beat_resolution * (0.5 + np.arange(0, num_beat))
        xtick_labels = np.arange(1, 1 + num_beat)
        ax.set_xticks(xticks_major)
        ax.set_xticklabels('')
        ax.set_xticks(xticks_minor, minor=True)
        ax.set_xticklabels(xtick_labels, minor=True)
        ax.tick_params(axis='x', which='minor', width=0)
        ax.set_xlabel('beats')
    ax.grid(axis='both', color='k', linestyle=':', linewidth=.5)
    return

def plot_four_units(units, unit_index, min_pitch, max_pitch):
    """
    Given an input dictionary containing "input", "input_next", "comp" and "comp_next",
    plot 2x2 subplots of the four unit pianorolls
    """
    fig, ax = plt.subplots(2,2)
    fig.set_size_inches(10, 6, forward=True)
    ax[0,0].set_title('Input')
    ax[0,1].set_title('Input next')
    ax[1,0].set_title('Comp')
    ax[1,1].set_title('Comp next')
    plot_pianoroll(ax[0,0], units["input"][unit_index], min_pitch, max_pitch, beat_resolution=24)
    plot_pianoroll(ax[0,1], units["input_next"][unit_index], min_pitch, max_pitch, beat_resolution=24)
    plot_pianoroll(ax[1,0], units["comp"][unit_index], min_pitch, max_pitch, beat_resolution=24)
    plot_pianoroll(ax[1,1], units["comp_next"][unit_index], min_pitch, max_pitch, beat_resolution=24)
    fig.tight_layout()
    return

def play_pianoroll(pianoroll, min_pitch=0, max_pitch=127, bpm=120.0, beat_resolution=24):
    """
    !!----------- Not widely supported ---------------!!
    Given an input pianoroll, creates a MIDI file in /tmp/
    and plays the MIDI file (requires TiMidity++ softsynth)
    [https://wiki.archlinux.org/index.php/timidity]
    
    Returns the exit code of timidity
    """
    FILEPATH = '/tmp/tmp.midi' # For Linux
    if min_pitch != 0 or max_pitch != 127:
        print(min_pitch, max_pitch)
        pianoroll = pad_pianoroll(pianoroll, min_pitch, max_pitch) # Pad to full 128 pitches
    track = pypianoroll.Track(pianoroll=pianoroll, program=0, is_drum=False, name='tmp')
    multitrack = pypianoroll.Multitrack(tracks=[track], tempo=bpm, beat_resolution=beat_resolution)
    pypianoroll.write(multitrack, FILEPATH)
    return_code = subprocess.call("timidity " + FILEPATH, shell=True)
    return return_code

def play_pianoroll_events(pianoroll, min_pitch=0, max_pitch=127):
    return play_midi_events(pianoroll_2_events(pianoroll, min_pitch, max_pitch))

def play_midi_events(events):
    COMP_CHANNEL = 5
    beats_per_bar = 4
    ticks_per_beat = 24

    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)
    # Loop through every tick in every beat
    for beat in range(beats_per_bar):
        # Play recorded messages and wait at each tick
        for tick in range(ticks_per_beat):
            current_tick = beat*ticks_per_beat + tick
            for msg in events[current_tick]:
                track.append(msg.copy(channel=COMP_CHANNEL, time=0))
            # This effectively acts as a time.sleep for 1 tick
            track.append(Message('note_off', note=0, velocity=0, time=16))
    FILEPATH = '/tmp/tmp_.midi' # For Linux
    mid.save(FILEPATH)
    return_code = subprocess.call("timidity " + FILEPATH, shell=True)
    return return_code

def pianoroll_2_events(pianoroll, min_pitch=0, max_pitch=127):
    """
    Takes an input pianoroll of shape (NUM_PITCHES, NUM_TICKS) 
    and returns a list of quantized events
    "Adjacent nonzero values of the same pitch will be considered a 
    single note with their mean as its velocity.", as per pypianoroll.
    https://github.com/salu133445/pypianoroll/blob/master/pypianoroll/multitrack.py#L1171
    """
    assert pianoroll.shape[0] == max_pitch - min_pitch + 1
    num_pitches = pianoroll.shape[0]
    num_ticks = pianoroll.shape[1]
    pianoroll = pianoroll.T
    
    events = [[] for _ in range(num_ticks)] # Each tick gets a list to store events
    clipped = pianoroll.astype(int)
    binarized = clipped.astype(bool)
    padded = np.pad(binarized, ((1, 1), (0, 0)), 'constant')
    diff = np.diff(padded.astype(int), axis=0)

    for p in range(num_pitches):
        pitch = min_pitch + p
        note_ons = np.nonzero(diff[:, pitch] > 0)[0]
        note_offs = np.nonzero(diff[:, pitch] < 0)[0]
        for idx, note_on in enumerate(note_ons):
            velocity = np.mean(clipped[note_on:note_offs[idx], p])
            # Create message events
            on_msg = mido.Message('note_on', note=pitch, velocity=int(velocity), time=0)
            events[note_ons[idx]].append(on_msg)
            if note_offs[idx] < num_ticks:
                off_msg = mido.Message('note_on', note=pitch, velocity=0, time=0)
                events[note_offs[idx]].append(off_msg)
    return events

def get_transposed_pianoroll(pianoroll, num_semitones):
    """
    Given an input pianoroll matrix of shape [NUM_TICKS, NUM_PITCHES],
    musically-transpose the pianoroll by num_semitones and
    return the new transposed pianoroll.
    """
    num_ticks = pianoroll.shape[0]
    num_pitches = pianoroll.shape[1]
    assert(abs(num_semitones) <= num_pitches)
    
    # Default case, no transposition
    transposed_pianoroll = pianoroll
    # Transpose up
    if (num_semitones > 0):
        transposed_pianoroll = np.hstack([np.zeros(num_semitones*num_ticks).reshape(num_ticks,num_semitones),
                                          pianoroll[:,:num_pitches-num_semitones] ])
    # Transpose down
    elif (num_semitones < 0):
        num_semitones = abs(num_semitones)
        transposed_pianoroll = np.hstack([pianoroll[:,num_semitones:],
                                          np.zeros(num_semitones*num_ticks).reshape(num_ticks,num_semitones) ])
    # Debug assertion
    assert(transposed_pianoroll.shape == (num_ticks, num_pitches))
    return transposed_pianoroll



def chop_to_unit_multiple(pianoroll, ticks_per_unit):
    """
    Given an input pianoroll matrix of shape [NUM_TICKS, NUM_PITCHES],
    truncate the matrix so that it can be evenly divided into M units.
    
    Returns [M, pianoroll_truncated]
    where M is the largest integer such that M*ticks_per_unit <= NUM_TICKS
    and pianoroll_truncated is of shape [M*ticks_per_unit, NUM_PITCHES]
    """
    
    num_ticks = pianoroll.shape[0]
    num_pitches = pianoroll.shape[1]
    
    # Get M
    M = int(num_ticks / ticks_per_unit) # Floor
    # Truncate
    pianoroll_truncated = pianoroll[:M*ticks_per_unit, :]
    
    # Debug assertions
    assert(M*ticks_per_unit <= num_ticks)
    assert(pianoroll_truncated.shape == (M*ticks_per_unit, num_pitches))
    
    return [M, pianoroll_truncated]


def shuffle_left_right(left_units, right_units):
    """
    Given 2 matrices of left and right pianorolls units,
    return 2 matrices which have left and right randomly exchanged
    while maintaining index order, eg:
    
    [a1,a2,a3,a4]  ->  [a1,b2,b3,a4]
    [b1,b2,b3,b4]      [b1,a2,a3,b4]
    """
    
    bool_array = np.random.randint(0, 2, left_units.shape[0], dtype=bool) # Random True/False
    
    # Initialize as copies of one side of the accompaniment
    input_units = left_units.copy()
    comp_units = right_units.copy()

    # Replace half of array with elements from the other side
    input_units[bool_array, ...] = right_units[bool_array, ...]
    comp_units[bool_array, ...] = left_units[bool_array, ...]
    
    return [input_units, comp_units]


def create_units(pianoroll, num_pitches, ticks_per_unit, partition_note, min_pitch=0, filter_threshold=0):
    """
    Given an input pianoroll matrix of shape [NUM_TICKS, NUM_PITCHES], 
    return input_units and comp_units of shape [M, TICKS PER UNIT, NUM_PITCHES]
    """
    assert(pianoroll.shape[1] == num_pitches)
    
    # Truncate pianoroll so it can be evenly divided into units
    [M, pianoroll] = chop_to_unit_multiple(pianoroll, ticks_per_unit)
    
    # Prepare outputs
    input_units = np.zeros([M, ticks_per_unit, num_pitches])
    comp_units = np.zeros([M, ticks_per_unit, num_pitches])
    
    # Split pianoroll into left- and right- accompaniments
    partition_note = partition_note - min_pitch
    left_comp = pianoroll.copy()
    left_comp[:, partition_note:] = 0
    right_comp = pianoroll.copy()
    right_comp[:, :partition_note] = 0
    
    # Get the units by reshaping left_comp and right_comp
    left_units = left_comp.reshape(M, ticks_per_unit, num_pitches)
    right_units = right_comp.reshape(M, ticks_per_unit, num_pitches)
    
    # Randomly choose between left/right for input/comp units, 
    # so the model learns both sides of the accompaniment
    [input_units, comp_units] = shuffle_left_right(left_units, right_units)
    
    # Filter out near-empty units
    input_units_means = np.mean(input_units, axis=(1,2)).squeeze()
    filter_array = input_units_means > filter_threshold
    input_units = input_units[filter_array, ...]
    comp_units = comp_units[filter_array, ...]
    M = np.sum(filter_array) # Recount M after filtering
    
    # Debug assertions
    assert(input_units.shape == (M, ticks_per_unit, num_pitches))
    assert(comp_units.shape == (M, ticks_per_unit, num_pitches))
    
    return [input_units, comp_units]
