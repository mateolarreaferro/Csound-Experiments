<CsoundSynthesizer>
<CsOptions>
-odac -d
</CsOptions>
<CsInstruments>

sr = 44100
ksmps = 100
nchnls = 2
0dbfs = 1.0

; Common waveform tables
gisine   ftgen 1, 0, 16384, 10, 1
gisquare ftgen 2, 0, 16384, 10, 1, 0, .33, 0, .2, 0, .14, 0, .11, 0, .09
gisaw    ftgen 3, 0, 16384, 10, 1, .2, 0, .4, 0, .6, 0, .8, 0, 1, 0, .8, 0, .6, 0, .4, 0, .2

; Scale tables
giscale1 ftgen 111, 0, 8, -2, 72, 74, 76, 79, 81, 83, 72, 84
giscale2 ftgen 112, 0, 8, -2, 52, 50, 48, 65, 60, 52, 48, 60
giscale3 ftgen 113, 0, 8, -2, 60, 62, 69, 67, 71, 74, 72, 48
giscale4 ftgen 114, 0, 8, -2, 48, 43, 50, 48, 43, 55, 60, 43

; Reverb globals
garvbL init 0
garvbR init 0

; Delay globals
gadelL init 0
gadelR init 0

; BCI globals - using alpha band power from first 4 channels
gkf1 init 0.5
gkf2 init 0.5
gkf3 init 0.5
gkf4 init 0.5

; Schedule instruments
schedule 1, 0, -1        ; BCI OSC Listener
schedule 3, 0, -1        ; Reverb
schedule 4, 0, -1        ; Delay

; MIDI setup
massign 1, 2

; ==============================================================================
; Instrument 1: OpenBCI Band Power Listener
; ==============================================================================
instr 1
    ; Initialize OSC handle
    gihandle OSCinit 5003
    
    ; Local variables for band power data [delta, theta, alpha, beta, gamma]
    kdelta1, ktheta1, kalpha1, kbeta1, kgamma1 init 0
    kdelta2, ktheta2, kalpha2, kbeta2, kgamma2 init 0  
    kdelta3, ktheta3, kalpha3, kbeta3, kgamma3 init 0
    kdelta4, ktheta4, kalpha4, kbeta4, kgamma4 init 0
    
    ; Listen to OpenBCI band power data (first 4 channels)
    kk1 OSClisten gihandle, "/openbci/band-power/0", "fffff", kdelta1, ktheta1, kalpha1, kbeta1, kgamma1
    kk2 OSClisten gihandle, "/openbci/band-power/1", "fffff", kdelta2, ktheta2, kalpha2, kbeta2, kgamma2
    kk3 OSClisten gihandle, "/openbci/band-power/2", "fffff", kdelta3, ktheta3, kalpha3, kbeta3, kgamma3
    kk4 OSClisten gihandle, "/openbci/band-power/3", "fffff", kdelta4, ktheta4, kalpha4, kbeta4, kgamma4
    
    ; Extract and scale alpha band values (index 2 of the 5 bands)
    if kk1 > 0 then
        gkf1 = kalpha1 * 0.0001  ; Scale from power values (typically 1000s) to synthesis range
    endif
    if kk2 > 0 then
        gkf2 = kalpha2 * 0.0001
    endif
    if kk3 > 0 then
        gkf3 = kalpha3 * 0.0001
    endif
    if kk4 > 0 then
        gkf4 = kalpha4 * 0.0001
    endif
    
    ; Optional: Use other bands - uncomment to experiment
    ; Beta band (high focus/attention):
    ; if kk1 > 0 then
    ;     gkf1 = kbeta1 * 0.0001
    ; endif
    
    ; Theta band (creativity/meditation):
    ; if kk1 > 0 then
    ;     gkf1 = ktheta1 * 0.0001
    ; endif
    
    ; Fallback smoothing when no data received
    if kk1 == 0 then
        gkf1 = gkf1 * 0.995 + 0.5 * 0.005
    endif
    if kk2 == 0 then
        gkf2 = gkf2 * 0.995 + 0.5 * 0.005
    endif
    if kk3 == 0 then
        gkf3 = gkf3 * 0.995 + 0.5 * 0.005
    endif
    if kk4 == 0 then
        gkf4 = gkf4 * 0.995 + 0.5 * 0.005
    endif
    
    ; Connection monitoring and debug output
    ktimer timeinsts
    if kk1 > 0 || kk2 > 0 || kk3 > 0 || kk4 > 0 then
        printks "Alpha power: %.4f %.4f %.4f %.4f\n", 1, gkf1, gkf2, gkf3, gkf4
    elseif ktimer > 5 && int(ktimer) % 5 == 0 then
        printks "Waiting for OpenBCI band power data...\n", 5
    endif
endin

; ==============================================================================
; Instrument 2: MIDI-controlled Synthesis with BCI modulation
; ==============================================================================
instr 2
    ; MIDI CC controls with fallback defaults
    kspeed1 midic7 21, .01, 40
    kspeed2 midic7 22, .01, 50
    kspeed3 midic7 23, .01, 100
    kspeed4 midic7 24, .01, 10
    
    ; Use defaults if no MIDI controller
    if kspeed1 == 0 then
        kspeed1 = 10
    endif
    if kspeed2 == 0 then
        kspeed2 = 15
    endif
    if kspeed3 == 0 then
        kspeed3 = 25
    endif
    if kspeed4 == 0 then
        kspeed4 = 5
    endif
    
    ; Create metro triggers
    ktrig1 metro kspeed1
    ktrig2 metro kspeed2
    ktrig3 metro kspeed3
    ktrig4 metro kspeed4
    
    ; Sample and hold BCI values
    kf1 samphold gkf1, ktrig1
    kf2 samphold gkf2, ktrig2
    kf3 samphold gkf3, ktrig3
    kf4 samphold gkf4, ktrig4
    
    ; Scale BCI values for pitch modulation (ensure they're in good range)
    kf1_scaled = abs(kf1) * 3 + 0.2  ; Scale and offset for musical range
    kf2_scaled = abs(kf2) * 3 + 0.2
    kf3_scaled = abs(kf3) * 3 + 0.2
    kf4_scaled = abs(kf4) * 3 + 0.2
    
    ; Get MIDI note frequency
    icps cpsmidi
    
    ; Generate oscillators modulated by BCI alpha waves
    aout1 oscili 0.5, icps + cpspch(kf1_scaled + 2), 1
    aout2 oscili 0.5, icps + cpspch(kf2_scaled + 2), 1
    aout3 oscili 0.5, icps + cpspch(kf3_scaled + 2), 1
    aout4 oscili 0.5, icps + cpspch(kf4_scaled + 2), 1
    
    ; Apply ADSR envelope
    aadsr madsr 1, 0.5, 0.8, 0.9
    
    ; Mix all oscillators
    aout = ((aout1 + aout2 + aout3 + aout4) / 8) * aadsr
    
    ; Send to effects
    garvbL += aout * 0.8
    garvbR += aout * 0.8
    gadelL += aout * 0.8
    gadelR += aout * 0.8
    
    ; Direct output
    outs aout, aout
endin

; ==============================================================================
; Instrument 3: Reverb
; ==============================================================================
instr 3
    denorm garvbL
    denorm garvbR
    aout1, aout2 reverbsc garvbL, garvbR, 0.8, 8000
    outs aout1, aout2
    clear garvbL
    clear garvbR
endin

; ==============================================================================
; Instrument 4: Delay
; ==============================================================================
instr 4
    adelL init 0
    adelR init 0
    denorm gadelL
    denorm gadelR
    adelL delay gadelL + (adelL * 0.72), 2
    adelR delay gadelR + (adelR * 0.7), 2
    adelOutL moogvcf adelL, 2000, 0.4
    adelOutR moogvcf adelR, 2000, 0.6
    outs adelOutL, adelOutR
    clear gadelL
    clear gadelR
endin

</CsInstruments>
<CsScore>
; Empty score - all instruments scheduled in orchestra
</CsScore>

</CsoundSynthesizer>
<bsbPanel>
 <label>Widgets</label>
 <objectName/>
 <x>100</x>
 <y>100</y>
 <width>320</width>
 <height>240</height>
 <visible>true</visible>
 <uuid/>
 <bgcolor mode="background">
  <r>240</r>
  <g>240</g>
  <b>240</b>
 </bgcolor>
</bsbPanel>
<bsbPresets>
</bsbPresets>
