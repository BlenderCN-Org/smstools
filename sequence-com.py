#!/usr/bin/env python2
# Converts Zelda/Mario sequence files (*.bms, *.com, yaz0 *.szs) to MIDI
# Requires python-midi (https://github.com/avsaj/python-midi)
# It's quite a mess, but fairly capable. I need to decide if I should rewrite/refactor it or port/contribute to the other one

# broken in Windows Media Player: k_manma, t_casino_fanf, t_chuboss, t_delfino, t_event, t_mechakuppa_, t_pinnapaco, t_select, t_shilena
# broken in MuseScore: t_delfino, t_event, t_shilena

import struct, sys, os
from struct import unpack
from warnings import warn
import midi

def handlePerf(type, value, duration, maxValue, track, tick):
  event2 = None
  if type == 0:
    # volume
    event1 = midi.ControlChangeEvent(tick=tick)
    event1.control = 7 # Main Volume
    #if maxValue > 0x7F:
    #  event1.value = (value>>8)&0xFF
    #  event2 = midi.ControlChangeEvent(tick=0)
    #  event2.control = 39 # Volume LSB
    #  event2.value = value&0xFF
    #else:
    #  event1.value = value
    event1.value = (value*0x7F)/maxValue
  elif type == 1:
    # pitch
    event1 = midi.PitchWheelEvent(tick=tick)
    event1.pitch = (value*0x7FFF)/maxValue
  elif type == 3:
    # pan
    event1 = midi.ControlChangeEvent(tick=tick)
    event1.control = 10 # Pan
    #if maxValue > 0x7F:
    #  event1.value = (value>>8)&0xFF
    #  event2 = midi.ControlChangeEvent(tick=0)
    #  event2.control = 42 # Pan LSB
    #  event2.value = value&0xFF
    #else:
    #  event1.value = value
    event1.value = (value*0x7F)/maxValue
  else:
    warn("Unknown perf type %d"%type)
    event1 = midi.TextMetaEvent(tick=tick, data=map(ord, "Perf %d (%d)"%(type, value)))
  track.append(event1)
  if event2 is not None: track.append(event2)
  if duration:
    if type == 0:
      # volume
      event = midi.ControlChangeEvent(tick=duration)
      event.control = 7 # Main Volume
      event.value = 0x7F
    elif type == 1:
      # pitch
      event = midi.PitchWheelEvent(tick=duration)
      event.pitch = 0x2000
    elif type == 3:
      # pan
      event = midi.ControlChangeEvent(tick=duration)
      event.control = 10 # Pan
      event.value = 0x40
    else:
      event = midi.TextMetaEvent(tick=duration, data=map(ord, "Perf %d (%d)"%(type, value)))
    return event

def handleBankProgram(which, selection, track, tick):
  if which == 7:
    # pitch
    print "Pitch", selection
    event = midi.ControlChangeEvent(tick=tick)
    event.control = 101 # RPN MSB
    event.value = 0
    track.append(event)
    event = midi.ControlChangeEvent(tick=0)
    event.control = 100 # RPN LSB
    event.value = 0
    track.append(event)
    event = midi.ControlChangeEvent(tick=0)
    event.control = 6 # Data entry MSB
    event.value = selection
    track.append(event)
    event = midi.ControlChangeEvent(tick=0)
    event.control = 38 # Data entry LSB
    event.value = 0
    track.append(event)
  elif which == 0x20:
    # bank
    print "Bank", selection
    event = midi.ControlChangeEvent(tick=tick)
    event.control = 32 # Bank Select
    event.value = selection
    track.append(event)
  elif which == 0x21:
    # program
    print "Program", selection
    event = midi.ProgramChangeEvent(tick=tick, value=selection%128)
    track.append(event)
  else:
    warn("Unknown bank/program %x (%d)"%(which, selection))
    event = midi.TextMetaEvent(tick=tick, data=map(ord, "Bank/Program %d (%d)"%(which, selection)))
    track.append(event)

def handleSeek(type, mode, point, track, tick, voices):
  #print ("Call", "Ret", "Jump")[(type-0xC3)/2], mode, point
  if mode == 0: pass # always
  elif mode == 1: pass # zero
  elif mode == 2: pass # nonzero
  elif mode == 3: pass # one
  elif mode == 4: pass # greater than
  elif mode == 5: pass # less than
  else: warn("Unknown seek mode %d"%mode)
  # stop all notes before looping
  voicepairs = voices.items()
  if 0:#type in (0xC5, 0xC6, 0xC7, 0xC8): # Jump
    for voiceId, note in voicepairs:
      noteOff = midi.NoteOffEvent(tick=tick, pitch=note)
      tick = 0
      track.append(noteOff)
      del voices[voiceId]
  return tick

def doNoteOffBurp(voiceId, track, tick, voices):
  voiceNoteOns = voices[voiceId]
  voiceNoteOns.sort(key=lambda a: a.tick)
  noteOn = None
  for i in range(len(voiceNoteOns)):
    if voiceNoteOns[i].tick >= tick:
      if i > 0:
        noteOn = voiceNoteOns[i-1]
        del voiceNoteOns[i-1]
      break
  if noteOn is not None:
    noteOff = midi.NoteOffEvent(tick=tick, pitch=noteOn.pitch)
    track.append(noteOff)

def doNoteOff(voiceId, track, tick, voices):
  if voiceId in voices:
    noteOff = midi.NoteOffEvent(tick=tick, pitch=voices[voiceId])
    track.append(noteOff)
    del voices[voiceId]
  else:
    warn("No voiceId %d to turn off"%voiceId)

def readTrack(fin, pattern=None, trackId=-1, delay=0, endTime=-1, maxpos=-1):
  trackWasInit = False
  stack = []
  totalTime = delay
  if pattern is not None:
    #voices = [[] for i in range(8)]
    voices = {}
    track = midi.Track()
    pattern.append(track)
    queuedEvents = []
  tracksToDo = []
  channel = (trackId)%16
  if trackId == 15: channel = 9
  while True:
    #if fin.tell() >= maxpos and maxpos != -1:
      #warn("Passed track bounds")
      #break
    #print hex(fin.tell()),
    #print totalTime,
    c = fin.read(1)
    if c == '': break
    cmd = ord(c)
    if cmd in (0x80, 0x88, 0xF0, 0xB8):
      # delay
      nextDelay, = unpack('>B', fin.read(1)) if cmd in (0xF0, 0x80) else unpack('>H', fin.read(2))
      delay += nextDelay
      totalTime += nextDelay
      #print "Delay", hex(cmd), nextDelay
      if pattern is not None:
        queuedEvents.sort(key=lambda e: 0 if e is None else e.tick)
        i = 0
        while i < len(queuedEvents):
          event = queuedEvents[i]
          if event is None:
            del queuedEvents[i]
            continue
          #if i > 0 and queuedEvents[i-1].tick == event.tick:
          #  del queuedEvents[i]
          #  continue
          i += 1
        while i < len(queuedEvents):
          event = queuedEvents[i]
          event.tick -= nextDelay
          if event.tick <= 0:
            nextTick = -event.tick
            event.tick = delay+event.tick
            track.append(event)
            delay = nextTick
            del queuedEvents[i]
          else:
            i += 1
    elif cmd == 0x94:
      # perf
      type, value = unpack('>BB', fin.read(2))
      #print "Perf", type, value, 0
      if pattern is not None: queuedEvents.append(handlePerf(type, value, 0, 0xFF, track, delay))
      delay = 0
    elif cmd == 0x96:
      # perf
      type, value, duration = unpack('>BBB', fin.read(3))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0xFF, track, delay))
      delay = 0
    elif cmd == 0x97:
      # perf
      type, value, duration = unpack('>BBH', fin.read(4))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0xFF, track, delay))
      delay = 0
    elif cmd == 0x98:
      # perf
      type, value = unpack('>Bb', fin.read(2))
      #print "Perf", type, value, 0
      if pattern is not None: queuedEvents.append(handlePerf(type, value, 0, 0x7F, track, delay))
      delay = 0
    elif cmd == 0x9A:
      # perf
      type, value, duration = unpack('>BbB', fin.read(3))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0x7F, track, delay))
      delay = 0
    elif cmd == 0x9B:
      # perf
      type, value, duration = unpack('>BbH', fin.read(4))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0x7F, track, delay))
      delay = 0
    elif cmd == 0x9C:
      # perf
      type, value = unpack('>Bh', fin.read(3))
      #print "Perf", type, value, 0
      if pattern is not None: queuedEvents.append(handlePerf(type, value, 0, 0x7FFF, track, delay))
      delay = 0
    elif cmd == 0x9E:
      # perf
      type, value, duration = unpack('>BhB', fin.read(4))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0x7FFF, track, delay))
      delay = 0
    elif cmd == 0x9F:
      # perf
      type, value, duration = unpack('>BhH', fin.read(5))
      #print "Perf", type, value, duration
      if pattern is not None: queuedEvents.append(handlePerf(type, value, duration, 0x7FFF, track, delay))
      delay = 0
    elif cmd == 0xA4:
      which, selection = unpack('>BB', fin.read(2))
      if pattern is not None: handleBankProgram(which, selection, track, delay)
      else:
        if which == 0x20: print "Bank", selection
        elif which == 0x21: print "Program", selection
        else: warn("Unknown bank/program %x (%d)"%(which, selection))
      if which == 0x21 and selection > 127:
        channel = 9
      delay = 0
    elif cmd == 0xAC:
      which, selection = unpack('>BH', fin.read(3))
      if pattern is not None: handleBankProgram(which, selection, track, delay)
      else:
        if which == 0x20: print "Bank", selection
        elif which == 0x21: print "Program", selection
        else: warn("Unknown bank/program %x (%d)"%(which, selection))
      if which == 0x21 and selection > 127:
        channel = 9
      delay = 0
    elif cmd == 0xB8:
      warn("Unknown B8")
      fin.seek(2,1)
    elif cmd == 0xB9:
      warn("Unknown B9")
      fin.seek(3,1)
    elif cmd == 0xC1:
      # child track pointer
      # cmdOpenTrack
      childTrackId, tmp, trackPos = unpack('>BBH', fin.read(4))
      trackPos |= tmp<<16
      print "New track", childTrackId, "at", hex(trackPos), "delay", delay
      tracksToDo.append((trackPos, childTrackId, delay))
    elif cmd == 0xC2:
      # sibling track
      # cmdOpenTrackBros
      raise NotImplementedError("")
    elif cmd == 0xC3:
      warn("Unknown C3, prob call")
      mode, point = unpack('>BH', fin.read(3))
      if pattern is not None: delay = handleSeek(0xC3, mode, point, track, delay, voices)
      stack.append(fin.tell())
      fin.seek(point)
    elif cmd == 0xC4:
      # cmdCall
      mode, tmp, point = unpack('>BBH', fin.read(4))
      point |= tmp<<16
      if pattern is not None: delay = handleSeek(0xC4, mode, point, track, delay, voices)
      stack.append(fin.tell())
      fin.seek(point)
    elif cmd == 0xC5:
      warn("Unknown C5, prob return")
      mode, = unpack('>B', fin.read(1))
      point = stack.pop()
      if pattern is not None: delay = handleSeek(0xC5, mode, point, track, delay, voices)
      fin.seek(point)
    elif cmd == 0xC6:
      # back
      # cmdRet
      mode, = unpack('>B', fin.read(1))
      point = stack.pop()
      if pattern is not None: delay = handleSeek(0xC6, mode, point, track, delay, voices)
      fin.seek(point)
    elif cmd == 0xC7:
      warn("Unknown C7, prob jump")
      mode, point = unpack('>BH', fin.read(3))
      if pattern is not None: delay = handleSeek(0xC7, mode, point, track, delay, voices)
      if 1:#totalTime < endTime: fin.seek(point)
      #else:
        track.append(midi.TextMetaEvent(tick=delay, data=map(ord, "Jump to 0x%X"%(point))))
        delay = 0
        if mode == 0:
          print "Breaking out of loop"
          break
    elif cmd == 0xC8:
      # seek ex
      # cmdJmp
      mode, tmp, point = unpack('>BBH', fin.read(4))
      point |= tmp<<16
      if pattern is not None: delay = handleSeek(0xC8, mode, point, track, delay, voices)
      if 1:#totalTime < endTime: fin.seek(point)
      #else:
        track.append(midi.TextMetaEvent(tick=delay, data=map(ord, "Jump to 0x%X"%(point))))
        delay = 0
        if mode == 0:
          print "Breaking out of loop"
          break
    elif cmd == 0xC9:
      # loop begin
      # cmdLoopS
      raise NotImplementedError("")
    elif cmd == 0xCA:
      # loop end
      # cmdLoopE
      raise NotImplementedError("")
    # 0xcb 0x8027eb54 cmdReadPort__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xcc 0x8027ebac cmdWritePort__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xcd 0x8027ed80 cmdCheckPortImport__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xce 0x8027ed98 cmdCheckPortExport__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xCF:
      # delay
      # cmdWait
      raise NotImplementedError("")
    # 0xD1 0x8027ebe0 cmdParentWritePort__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xD2 0x8027ec68 cmdChildWritePort__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xD4:
      # prev note
      # cmdSetLastNote
      raise NotImplementedError("")
    # 0xd5 0x8027ee44 cmdTimeRelate__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xd6 0x8027ee5c cmdSimpleOsc__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xd7 0x8027ee8c cmdSimpleEnv__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xd8 0x8027eec0 cmdSimpleADSR__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xD8:
      ppqn, = unpack('>xH', fin.read(3))
      warn("Unknown D8, prob PPQN %s"%ppqn)
      if pattern is not None: pattern.resolution = ppqn
    elif cmd == 0xD9:
      # transpose
      # cmdTranspose
      raise NotImplementedError("")
    elif cmd == 0xDA:
      # stop child
      # cmdCloseTrack
      raise NotImplementedError("")
    elif cmd == 0xDC:
      warn("Unknown DC")
      fin.seek(1,1)
    # 0xdc 0x8027f02c cmdUpdateSync__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xdd 0x8027f058 cmdBusConnect__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # TODO used by t_pinnapaco_m and k_kagemario
    elif cmd == 0xDD:
      warn("Unknown DD")
      fin.seek(3,1)
    elif cmd == 0xDE:
      # flags
      # cmdPauseStatus
      raise NotImplementedError("")
    elif cmd == 0xDF:
      # set dynamic
      # cmdSetInterrupt
      # TODO
      idx, tmp, point = unpack('>BBH', fin.read(4))
      point |= tmp<<16
      raise NotImplementedError("")
    elif cmd == 0xE0:
      # unset dynamic
      # cmdDisInterrupt
      #idx, = unpack('>B', fin.read(1))
	  #raise NotImplementedError("")
      tempo, = unpack('>H', fin.read(2))
      warn("Unknown E0, prob Tempo", tempo)
      if pattern is not None: track.append(midi.SetTempoEvent(bpm=tempo, tick=delay))
      delay = 0
    elif cmd == 0xE1:
      # clear dynamic
      # cmdClrI
      #raise NotImplementedError("")
      fin.seek(1,1)
    # 0xe2 0x8027f124 cmdSetI__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xE2:
      warn("Unknown E2")
      fin.seek(1,1)
    # 0xe3 0x8027f134 cmdRetI__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xE3:
      warn("Unknown E3")
      fin.seek(1,1)
    # 0xe4 0x8027f178 cmdIntTimer__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xE5:
      # add pool
      # cmdVibDepth
      raise NotImplementedError("")
    elif cmd == 0xE6:
      # remove pool
      # cmdVibDepthMidi
      raise NotImplementedError("")
    elif cmd == 0xE7:
      # track init
      # cmdSyncCPU
      arg, = unpack('>h', fin.read(2))
      print "Track init", arg
      if trackWasInit:
        raise Exception("Track was already initialized")
      else:
        trackWasInit = True
    # 0xe8 0x8027f1ec cmdFlushAll__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xe9 0x8027f214 cmdFlushRelease__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xEA:
      # delay
      # cmdWait
      raise NotImplementedError("")
    # 0xEB 0x8027f2ac cmdPanPowSet__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xEC 0x8027f544 cmdIIRSet__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xED 0x8027f330 cmdFIRSet__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xEE 0x8027f368 cmdEXTSet__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xEF? 0x8027f3bc cmdPanSwSet__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # TODO used by t_pinnapaco_m and k_kagemario
    elif cmd == 0xEF:
      warn("Unknown EF")
      fin.seek(3, 1)
    # 0xF0 0x8027f460 cmdOscRoute__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    elif cmd == 0xF0:
      warn("Unknown F0", hex(ord(fin.read(1))))
    # 0xF1 0x8027f5c8 cmdIIRCutOff__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xF2 0x8027f65c cmdOscFull__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xF3 0x8027f098 cmdVolumeMode__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0x?? 0x8027f4fc cmdVibPitch__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xFA 0x8027f698 cmdCheckWave__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xFB 0x8027f6a8 cmdPrintf__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    # 0xFC 0x8027f2a4 cmdNop__Q28JASystem10TSeqParserFPQ28JASystem6TTrackPUl
    
    elif cmd == 0xF9:
      warn("Unknown F9")
      fin.seek(2,1)
    elif cmd == 0xFD:
      # tempo
      # cmdTempo
      tempo, = unpack('>H', fin.read(2))
      print "Tempo", tempo
      if pattern is not None: track.append(midi.SetTempoEvent(bpm=tempo, tick=delay))
      delay = 0
    elif cmd == 0xFE:
      # PPQN (pulses per quarter note)
      # cmdTimeBase
      ppqn, = unpack('>H', fin.read(2))
      print "PPQN", ppqn
      if pattern is not None:
        pattern.resolution = ppqn
    elif cmd == 0xFF:
      # end track
      # cmdFinish
      print "End track"
      if pattern is not None: track.append(midi.EndOfTrackEvent(tick=delay))
      delay = 0
      break
    elif cmd < 0x90:
      # note
      if (cmd&0x88) == 0x88:
        # voice off
        voiceId = cmd & 0x07
        unk, = struct.unpack('>B', fin.read(1))
        #print "Voice off", voiceId, unk
        if pattern is not None:
          doNoteOff(voiceId, track, delay, voices)
        delay = 0
      elif (cmd&0x80) == 0x80:
        # voice off
        voiceId = cmd & 0x07
        #print "Voice off", voiceId
        if pattern is not None:
          doNoteOff(voiceId, track, delay, voices)
        delay = 0
      else:
        # voice on
        note = cmd
        flags, velocity = struct.unpack('>BB', fin.read(2))
        voiceId = flags&0x07
        flags &= 0xF8
        #print "Voice on", cmd, voiceId, velocity
        if pattern is not None and flags == 0:
          if voiceId in voices:
            warn("Voice id %d already on!"%voiceId)
          if note in voices.values():
            warn("Note %d already on!"%note)
          if velocity == 0:
            velocity = 1
          noteOn = midi.NoteOnEvent(tick=delay, pitch=note, velocity=velocity)
          track.append(noteOn)
          #voices[voiceId].append(noteOn)
          voices[voiceId] = note
          delay = 0
    else:
      warn("Unknown command %x@%x"%(cmd,fin.tell()))
      print hex(fin.tell())
      break
  if pattern is not None:
    if len(track) > 0 and not isinstance(track[-1], midi.EndOfTrackEvent):
      track.append(midi.EndOfTrackEvent(tick=delay))
      delay=0
    for event in track:
      event.channel = channel
  for i, (trackPos, childTrackId, delay) in enumerate(tracksToDo):
    #if childTrackId == 15: continue
    print "Track", childTrackId
    fin.seek(trackPos)
    readTrack(fin, pattern, childTrackId, delay, totalTime, tracksToDo[i+1][0] if i+1 < len(tracksToDo) else maxpos)

import os
if len(sys.argv) > 1: files = sys.argv[1:]
else: files = os.listdir('.')
for fname in files:
  if fname.endswith(".com") or fname.endswith(".bms") or len(sys.argv) > 1:
    print fname
    fin = open(fname, 'rb')
    pattern = midi.Pattern()
    fin.seek(0,2)
    maxpos = fin.tell()-2
    fin.seek(0,0)
    try: readTrack(fin, pattern, maxpos=maxpos)
    except Exception, e:
      print e
      continue
    finally: print hex(fin.tell())
    #print pattern
    if pattern is not None: midi.write_midifile(os.path.splitext(fname)[0]+".mid", pattern)
    fin.close()
