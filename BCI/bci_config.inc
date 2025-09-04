; ==============================================================================
; BCI Configuration Include File
; Supports both Muse and OpenBCI devices
; ==============================================================================

; Device selection (0=Muse, 1=OpenBCI)
#define BCI_DEVICE #1#

; OSC Port Configuration
#define OSC_PORT #5003#

; Channel count for different devices
#if $BCI_DEVICE == 0
    #define BCI_CHANNELS #4#  ; Muse has 4 channels
#else
    #define BCI_CHANNELS #8#  ; OpenBCI has 8 channels
#end

; ==============================================================================
; OSC Path Definitions
; ==============================================================================

#if $BCI_DEVICE == 0
    ; Muse OSC paths
    #define PATH_DELTA_ABS #"/muse/elements/delta_absolute"#
    #define PATH_THETA_ABS #"/muse/elements/theta_absolute"#
    #define PATH_ALPHA_ABS #"/muse/elements/alpha_absolute"#
    #define PATH_BETA_ABS  #"/muse/elements/beta_absolute"#
    #define PATH_GAMMA_ABS #"/muse/elements/gamma_absolute"#
    #define PATH_RAW_EEG   #"/muse/eeg"#
    #define OSC_FORMAT_4CH #"ffff"#
    #define OSC_FORMAT_6CH #"ffffff"#
#else
    ; OpenBCI OSC paths (customize these based on your OpenBCI setup)
    #define PATH_DELTA_ABS #"/openbci/bands/delta"#
    #define PATH_THETA_ABS #"/openbci/bands/theta"#
    #define PATH_ALPHA_ABS #"/openbci/bands/alpha"#
    #define PATH_BETA_ABS  #"/openbci/bands/beta"#
    #define PATH_GAMMA_ABS #"/openbci/bands/gamma"#
    #define PATH_RAW_EEG   #"/openbci/raw"#
    #define OSC_FORMAT_4CH #"ffffffff"#  ; 8 channels for OpenBCI
    #define OSC_FORMAT_8CH #"ffffffff"#
#end

; ==============================================================================
; Frequency Band Ranges (Hz)
; ==============================================================================
#define DELTA_MIN #0.5#
#define DELTA_MAX #4#
#define THETA_MIN #4#
#define THETA_MAX #8#
#define ALPHA_MIN #8#
#define ALPHA_MAX #13#
#define BETA_MIN  #13#
#define BETA_MAX  #30#
#define GAMMA_MIN #30#
#define GAMMA_MAX #44#

; ==============================================================================
; Default Values and Fallbacks
; ==============================================================================
#define DEFAULT_BCI_VALUE #0.5#  ; Default value when no signal
#define SMOOTHING_FACTOR  #0.1#  ; Smoothing for BCI values
#define TIMEOUT_SECONDS   #2#    ; Timeout for BCI data

; ==============================================================================
; Global variables initialization macro
; ==============================================================================
#define INIT_BCI_GLOBALS(prefix) #
    g$prefix.f1 init $DEFAULT_BCI_VALUE
    g$prefix.f2 init $DEFAULT_BCI_VALUE
    g$prefix.f3 init $DEFAULT_BCI_VALUE
    g$prefix.f4 init $DEFAULT_BCI_VALUE
    g$prefix.f5 init $DEFAULT_BCI_VALUE
    g$prefix.f6 init $DEFAULT_BCI_VALUE
    g$prefix.f7 init $DEFAULT_BCI_VALUE
    g$prefix.f8 init $DEFAULT_BCI_VALUE
    g$prefix.timeout init 0
    g$prefix.connected init 0
#