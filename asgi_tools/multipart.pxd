# cython: language_level=3


cdef class BaseParser:

    cdef dict callbacks

    cdef void callback(self, str name, bytes data, int start, int end) except *

    cpdef void write(self, bytes data) except *

    cpdef void finalize(self)


cdef class QueryStringParser(BaseParser):

    cdef unsigned int cursize
    cdef unsigned int max_size
    cdef unsigned char state


cdef class MultipartParser(BaseParser):

    cdef unsigned int cursize
    cdef unsigned int max_size
    cdef unsigned char state
    cdef unsigned int index
    cdef short flags
    cdef int header_field_pos
    cdef int header_value_pos
    cdef int part_data_pos
    cdef bytes boundary
    cdef frozenset boundary_chars
    cdef list lookbehind
