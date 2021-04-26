# cython: language_level=3


cdef class Request(dict):

    cdef bint _is_read
    cdef bytes _body
    cdef dict _cookies
    cdef dict _media
    cdef object _form
    cdef object _headers
    cdef object _url

    cdef public object _receive
    cdef public object _send
