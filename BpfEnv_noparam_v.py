
#=========================================================================
# VBpfEnv_noparam_v.py
#=========================================================================
"""Provide a template of PyMTL wrapper to import verilated models.

This wrapper makes a Verilator-generated C++ model appear as if it were a
normal PyMTL model. This template is based on PyMTL v2.
"""

import os

from cffi import FFI

from pymtl3.datatypes import *
from pymtl3.dsl import Component, connect, InPort, OutPort, Wire, update, update_ff

#-------------------------------------------------------------------------
# BpfEnv_noparam
#-------------------------------------------------------------------------

class BpfEnv_noparam( Component ):
  id_ = 0

  def __init__( s, *args, **kwargs ):
    s._finalization_count = 0

    # initialize FFI, define the exposed interface
    s.ffi = FFI()
    s.ffi.cdef("""
      typedef struct {

        // Exposed port interface
        unsigned char * bpf_accept;        
        unsigned char * bpf_active;        
        unsigned char * bpf_enb;        
        unsigned char * bpf_mmap_ack;        
        unsigned short * bpf_mmap_addr;        
        unsigned char * bpf_mmap_rd;        
        unsigned int * bpf_mmap_rdata;        
        unsigned int * bpf_mmap_wdata;        
        unsigned char * bpf_mmap_wr;        
        unsigned short * bpf_packet_len;        
        unsigned char * bpf_packet_loss;        
        unsigned char * bpf_pram_bank_bpf;        
        unsigned char * bpf_pram_bank_rx;        
        unsigned char * bpf_pram_bank_tx;        
        unsigned short * bpf_pram_raddr;        
        unsigned int * bpf_pram_rdata;        
        unsigned short * bpf_pram_waddr;        
        unsigned int * bpf_pram_wdata;        
        unsigned char * bpf_pram_wr;        
        unsigned char * bpf_reject;        
        unsigned int * bpf_ret_value;        
        unsigned char * bpf_return;        
        unsigned char * bpf_start;        
        unsigned char * clk;        
        unsigned char * reset;

        // Verilator model
        void * model;

      } VBpfEnv_noparam_t;

      VBpfEnv_noparam_t * create_model( const char * );
      void destroy_model( VBpfEnv_noparam_t *);
      void comb_eval( VBpfEnv_noparam_t * );
      void seq_eval( VBpfEnv_noparam_t * );
      void assert_en( bool en );
      

    """)

    # Print the modification time stamp of the shared lib
    # print 'Modification time of {}: {}'.format(
    #   'libBpfEnv_noparam_v.so', os.path.getmtime( './libBpfEnv_noparam_v.so' ) )

    # Import the shared library containing the model. We defer
    # construction to the elaborate_logic function to allow the user to
    # set the vcd_file.
    s._ffi_inst = s.ffi.dlopen('./libBpfEnv_noparam_v.so')

    # increment instance count
    BpfEnv_noparam.id_ += 1

  def finalize( s ):
    """Finalize the imported component.

    This method closes the shared library opened through CFFI. If an imported
    component is not finalized explicitly (i.e. if you rely on GC to collect a
    no longer used imported component), importing a component with the same
    name before all previous imported components are GCed might lead to
    confusing behaviors. This is because once opened, the shared lib
    is cached by the OS until the OS reference counter for this lib reaches
    0 (you can decrement the reference counter by calling `dl_close()` syscall).

    Fortunately real designs tend to always have the same shared lib corresponding
    to the components with the same name. If you are doing translation testing and
    use the same component class name even if they refer to different designs,
    you might need to call `imported_object.finalize()` at the end of each test
    to ensure correct behaviors.
    """
    assert s._finalization_count == 0,      'Imported component can only be finalized once!'
    s._finalization_count += 1
    s._ffi_inst.destroy_model( s._ffi_m )
    s.ffi.dlclose( s._ffi_inst )
    s.ffi = None
    s._ffi_inst = None

  def __del__( s ):
    if s._finalization_count == 0:
      s._finalization_count += 1
      s._ffi_inst.destroy_model( s._ffi_m )
      s.ffi.dlclose( s._ffi_inst )
      s.ffi = None
      s._ffi_inst = None

  def construct( s, *args, **kwargs ):
    # Set up the VCD file name
    verilator_vcd_file = ""
    if 0:
      if False:
        verilator_vcd_file = ".verilator1.vcd"
      else:
        verilator_vcd_file = "BpfEnv_noparam.verilator1.vcd"

    # Convert string to `bytes` which is required by CFFI on python 3
    verilator_vcd_file = verilator_vcd_file.encode('ascii')

    # Construct the model
    s._ffi_m = s._ffi_inst.create_model( s.ffi.new("char[]", verilator_vcd_file) )

    # Buffer for line tracing
    s._line_trace_str = s.ffi.new('char[512]')
    s._convert_string = s.ffi.string

    # Use non-attribute varialbe to reduce CPython bytecode count
    _ffi_m = s._ffi_m
    _ffi_inst_comb_eval = s._ffi_inst.comb_eval
    _ffi_inst_seq_eval  = s._ffi_inst.seq_eval

    # declare the port interface
    s.bpf_accept = OutPort( Bits1 )
    s.bpf_active = OutPort( Bits1 )
    s.bpf_enb = OutPort( Bits1 )
    s.bpf_mmap_ack = OutPort( Bits1 )
    s.bpf_mmap_addr = InPort( Bits16 )
    s.bpf_mmap_rd = InPort( Bits1 )
    s.bpf_mmap_rdata = OutPort( Bits32 )
    s.bpf_mmap_wdata = InPort( Bits32 )
    s.bpf_mmap_wr = InPort( Bits1 )
    s.bpf_packet_len = InPort( Bits14 )
    s.bpf_packet_loss = InPort( Bits1 )
    s.bpf_pram_bank_bpf = InPort( Bits2 )
    s.bpf_pram_bank_rx = InPort( Bits2 )
    s.bpf_pram_bank_tx = InPort( Bits2 )
    s.bpf_pram_raddr = InPort( Bits14 )
    s.bpf_pram_rdata = OutPort( Bits32 )
    s.bpf_pram_waddr = InPort( Bits14 )
    s.bpf_pram_wdata = InPort( Bits32 )
    s.bpf_pram_wr = InPort( Bits1 )
    s.bpf_reject = OutPort( Bits1 )
    s.bpf_ret_value = OutPort( Bits32 )
    s.bpf_return = OutPort( Bits1 )
    s.bpf_start = InPort( Bits1 )

    # update blocks that converts ffi interface to/from pymtl ports
    
    s.s_DOT_bpf_mmap_addr = Wire( Bits16 )
    @update
    def isignal_s_DOT_bpf_mmap_addr():
      s.s_DOT_bpf_mmap_addr @= s.bpf_mmap_addr
    
    s.s_DOT_bpf_mmap_rd = Wire( Bits1 )
    @update
    def isignal_s_DOT_bpf_mmap_rd():
      s.s_DOT_bpf_mmap_rd @= s.bpf_mmap_rd
    
    s.s_DOT_bpf_mmap_wdata = Wire( Bits32 )
    @update
    def isignal_s_DOT_bpf_mmap_wdata():
      s.s_DOT_bpf_mmap_wdata @= s.bpf_mmap_wdata
    
    s.s_DOT_bpf_mmap_wr = Wire( Bits1 )
    @update
    def isignal_s_DOT_bpf_mmap_wr():
      s.s_DOT_bpf_mmap_wr @= s.bpf_mmap_wr
    
    s.s_DOT_bpf_packet_len = Wire( Bits14 )
    @update
    def isignal_s_DOT_bpf_packet_len():
      s.s_DOT_bpf_packet_len @= s.bpf_packet_len
    
    s.s_DOT_bpf_packet_loss = Wire( Bits1 )
    @update
    def isignal_s_DOT_bpf_packet_loss():
      s.s_DOT_bpf_packet_loss @= s.bpf_packet_loss
    
    s.s_DOT_bpf_pram_bank_bpf = Wire( Bits2 )
    @update
    def isignal_s_DOT_bpf_pram_bank_bpf():
      s.s_DOT_bpf_pram_bank_bpf @= s.bpf_pram_bank_bpf
    
    s.s_DOT_bpf_pram_bank_rx = Wire( Bits2 )
    @update
    def isignal_s_DOT_bpf_pram_bank_rx():
      s.s_DOT_bpf_pram_bank_rx @= s.bpf_pram_bank_rx
    
    s.s_DOT_bpf_pram_bank_tx = Wire( Bits2 )
    @update
    def isignal_s_DOT_bpf_pram_bank_tx():
      s.s_DOT_bpf_pram_bank_tx @= s.bpf_pram_bank_tx
    
    s.s_DOT_bpf_pram_raddr = Wire( Bits14 )
    @update
    def isignal_s_DOT_bpf_pram_raddr():
      s.s_DOT_bpf_pram_raddr @= s.bpf_pram_raddr
    
    s.s_DOT_bpf_pram_waddr = Wire( Bits14 )
    @update
    def isignal_s_DOT_bpf_pram_waddr():
      s.s_DOT_bpf_pram_waddr @= s.bpf_pram_waddr
    
    s.s_DOT_bpf_pram_wdata = Wire( Bits32 )
    @update
    def isignal_s_DOT_bpf_pram_wdata():
      s.s_DOT_bpf_pram_wdata @= s.bpf_pram_wdata
    
    s.s_DOT_bpf_pram_wr = Wire( Bits1 )
    @update
    def isignal_s_DOT_bpf_pram_wr():
      s.s_DOT_bpf_pram_wr @= s.bpf_pram_wr
    
    s.s_DOT_bpf_start = Wire( Bits1 )
    @update
    def isignal_s_DOT_bpf_start():
      s.s_DOT_bpf_start @= s.bpf_start
    
    s.s_DOT_reset = Wire( Bits1 )
    @update
    def isignal_s_DOT_reset():
      s.s_DOT_reset @= s.reset
    
    s.s_DOT_bpf_accept = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_accept():
      s.bpf_accept @= s.s_DOT_bpf_accept
    
    s.s_DOT_bpf_active = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_active():
      s.bpf_active @= s.s_DOT_bpf_active
    
    s.s_DOT_bpf_enb = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_enb():
      s.bpf_enb @= s.s_DOT_bpf_enb
    
    s.s_DOT_bpf_mmap_ack = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_mmap_ack():
      s.bpf_mmap_ack @= s.s_DOT_bpf_mmap_ack
    
    s.s_DOT_bpf_mmap_rdata = Wire( Bits32 )
    @update
    def osignal_s_DOT_bpf_mmap_rdata():
      s.bpf_mmap_rdata @= s.s_DOT_bpf_mmap_rdata
    
    s.s_DOT_bpf_pram_rdata = Wire( Bits32 )
    @update
    def osignal_s_DOT_bpf_pram_rdata():
      s.bpf_pram_rdata @= s.s_DOT_bpf_pram_rdata
    
    s.s_DOT_bpf_reject = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_reject():
      s.bpf_reject @= s.s_DOT_bpf_reject
    
    s.s_DOT_bpf_ret_value = Wire( Bits32 )
    @update
    def osignal_s_DOT_bpf_ret_value():
      s.bpf_ret_value @= s.s_DOT_bpf_ret_value
    
    s.s_DOT_bpf_return = Wire( Bits1 )
    @update
    def osignal_s_DOT_bpf_return():
      s.bpf_return @= s.s_DOT_bpf_return

    @update
    def comb_upblk():

      # Set inputs
      
      _ffi_m.bpf_mmap_addr[0] = int(s.s_DOT_bpf_mmap_addr)
      
      _ffi_m.bpf_mmap_rd[0] = int(s.s_DOT_bpf_mmap_rd)
      
      _ffi_m.bpf_mmap_wdata[0] = int(s.s_DOT_bpf_mmap_wdata)
      
      _ffi_m.bpf_mmap_wr[0] = int(s.s_DOT_bpf_mmap_wr)
      
      _ffi_m.bpf_packet_len[0] = int(s.s_DOT_bpf_packet_len)
      
      _ffi_m.bpf_packet_loss[0] = int(s.s_DOT_bpf_packet_loss)
      
      _ffi_m.bpf_pram_bank_bpf[0] = int(s.s_DOT_bpf_pram_bank_bpf)
      
      _ffi_m.bpf_pram_bank_rx[0] = int(s.s_DOT_bpf_pram_bank_rx)
      
      _ffi_m.bpf_pram_bank_tx[0] = int(s.s_DOT_bpf_pram_bank_tx)
      
      _ffi_m.bpf_pram_raddr[0] = int(s.s_DOT_bpf_pram_raddr)
      
      _ffi_m.bpf_pram_waddr[0] = int(s.s_DOT_bpf_pram_waddr)
      
      _ffi_m.bpf_pram_wdata[0] = int(s.s_DOT_bpf_pram_wdata)
      
      _ffi_m.bpf_pram_wr[0] = int(s.s_DOT_bpf_pram_wr)
      
      _ffi_m.bpf_start[0] = int(s.s_DOT_bpf_start)
      
      _ffi_m.reset[0] = int(s.s_DOT_reset)

      _ffi_inst_comb_eval( _ffi_m )

      # Write all outputs
      
      s.s_DOT_bpf_accept @= _ffi_m.bpf_accept[0]
      
      s.s_DOT_bpf_active @= _ffi_m.bpf_active[0]
      
      s.s_DOT_bpf_enb @= _ffi_m.bpf_enb[0]
      
      s.s_DOT_bpf_mmap_ack @= _ffi_m.bpf_mmap_ack[0]
      
      s.s_DOT_bpf_mmap_rdata @= _ffi_m.bpf_mmap_rdata[0]
      
      s.s_DOT_bpf_pram_rdata @= _ffi_m.bpf_pram_rdata[0]
      
      s.s_DOT_bpf_reject @= _ffi_m.bpf_reject[0]
      
      s.s_DOT_bpf_ret_value @= _ffi_m.bpf_ret_value[0]
      
      s.s_DOT_bpf_return @= _ffi_m.bpf_return[0]

    @update_ff
    def seq_upblk():
      # seq_eval will automatically tick clock in C land
      _ffi_inst_seq_eval( _ffi_m )

  def assert_en( s, en ):
    # TODO: for verilator, any assertion failure will cause the C simulator
    # to abort, which results in a Python internal error. A better approach
    # is to throw a Python exception at the time of assertion failure.
    # Verilator allows user-defined `stop` function which is called when
    # the simulation is expected to stop due to various reasons. We might
    # be able to raise a Python exception through Python C API (although
    # at this moment I'm not sure if the C API's are compatible between
    # PyPy and CPython).
    assert isinstance( en, bool )
    s._ffi_inst.assert_en( en )

  def line_trace( s ):
    if 0:
      s._ffi_inst.trace( s._ffi_m, s._line_trace_str )
      return s._convert_string( s._line_trace_str ).decode('ascii')
    else:
      return f' bpf_accept={s.bpf_accept}, bpf_active={s.bpf_active}, bpf_enb={s.bpf_enb}, bpf_mmap_ack={s.bpf_mmap_ack}, bpf_mmap_addr={s.bpf_mmap_addr}, bpf_mmap_rd={s.bpf_mmap_rd}, bpf_mmap_rdata={s.bpf_mmap_rdata}, bpf_mmap_wdata={s.bpf_mmap_wdata}, bpf_mmap_wr={s.bpf_mmap_wr}, bpf_packet_len={s.bpf_packet_len}, bpf_packet_loss={s.bpf_packet_loss}, bpf_pram_bank_bpf={s.bpf_pram_bank_bpf}, bpf_pram_bank_rx={s.bpf_pram_bank_rx}, bpf_pram_bank_tx={s.bpf_pram_bank_tx}, bpf_pram_raddr={s.bpf_pram_raddr}, bpf_pram_rdata={s.bpf_pram_rdata}, bpf_pram_waddr={s.bpf_pram_waddr}, bpf_pram_wdata={s.bpf_pram_wdata}, bpf_pram_wr={s.bpf_pram_wr}, bpf_reject={s.bpf_reject}, bpf_ret_value={s.bpf_ret_value}, bpf_return={s.bpf_return}, bpf_start={s.bpf_start}, clk={s.clk}, reset={s.reset},'

  def internal_line_trace( s ):
    return ''
